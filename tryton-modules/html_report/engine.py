import binascii
import io
import mimetypes
import os
import logging
import jinja2
import markdown
import subprocess
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import partial
from io import BytesIO
from urllib.parse import urlparse
from pypdf import PdfReader, PdfWriter
import re
import barcode
import qrcode
import qrcode.image.svg
from ppf.datamatrix import DataMatrix
import weasyprint
from babel import dates, numbers
from barcode.writer import SVGWriter

import trytond.config as config
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.model.fields.selection import TranslatedSelection
from trytond.model.modelstorage import _record_eval_pyson
from trytond.pool import Pool
from trytond.tools import file_open
from trytond.transaction import Transaction
from trytond.tools import grouped_slice
from trytond.report import Report
from trytond.modules.widgets import tools

from . import words
from .tools import label as tools_label

MEDIA_TYPE = config.get('html_report', 'type', default='screen')
DEFAULT_MIME_TYPE = config.get('html_report', 'mime_type', default='image/png')

# Determines if on merge, resulting PDF should be compacted using ghostscript
COMPACT_ON_MERGE = config.get('html_report', 'compact_on_merge',
    default=False)

logger = logging.getLogger(__name__)


def strfdelta(tdelta, fmt):
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    d['minutes'] = '%02d' % d['minutes']
    d['seconds'] = '%02d' % d['seconds']
    if not 'days' in fmt and d.get('days') > 0:
        d["hours"] += d.get('days') * 24 # 24h/day
    return fmt.format(**d)

def render(value, digits=2, lang=None, filename=None):
    if value is None or value == '':
        return ''
    if isinstance(value, str):
        return value.replace('\n', '<br/>')
    if isinstance(value, timedelta):
        return strfdelta(value, '{hours}:{minutes}')
    if isinstance(value, bool):
        return (gettext('html_report.msg_yes') if value else
            gettext('html_report.msg_no'))
    if isinstance(value, bytes):
        value = binascii.b2a_base64(value)
        value = value.decode('ascii')
        mimetype = None
        if filename:
            mimetype = mimetypes.guess_type(filename)[0]
        if not mimetype:
            mimetype = DEFAULT_MIME_TYPE
        return ('data:%s;base64,%s' % (mimetype, value)).strip()

    if not lang:
        context = Transaction().context
        lang = context.get('html_report_language')
        if not lang or isinstance(lang, str):
            logger.warning('html_report_language not found in context or is a '
                'string. Potential performance issue.')
            language = Transaction().language or 'en'
            Lang = Pool().get('ir.lang')
            langs = Lang.search([('code', '=', language)], limit=1)
            lang = langs[0] if langs else 'en'

    if isinstance(value, (float, Decimal)):
        context = Transaction().context
        grouping = not context.get('output_format') in ['xls', 'xlsx']
        return lang.format('%.*f', (digits, value), grouping=grouping)
    if isinstance(value, int):
        return lang.format('%d', value, grouping=True)
    if hasattr(value, 'rec_name'):
        return value.rec_name
    if isinstance(value, datetime):
        return lang.strftime(value)
    if isinstance(value, date):
        return lang.strftime(value)
    return value


class DualRecordError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class Formatter:
    def __init__(self):
        self.__langs = {}

    def format(self, record, field, value):
        formatter = '_formatted_%s' % field._type
        method = getattr(self, formatter, self._formatted_raw)
        return method(record, field, value)

    def _get_lang(self):
        Lang = Pool().get('ir.lang')
        locale = Transaction().context.get('report_lang', Transaction().language)
        lang = self.__langs.get(locale)
        if lang:
            return lang
        langs = Lang.search([('code', '=', locale or 'en')], limit=1)
        lang = langs[0] if langs else 'en'
        self.__langs[locale] = lang
        return lang

    def _formatted_raw(self, record, field, value):
        return value

    def _formatted_many2one(self, record, field, value):
        if not value:
            return value
        return FormattedRecord(value, self)

    def _formatted_one2one(self, record, field, value):
        return self._formatted_many2one(record, field, value)

    def _formatted_reference(self, record, field, value):
        return self._formatted_many2one(record, field, value)

    def _formatted_one2many(self, record, field, value):
        if not value:
            return value
        return [FormattedRecord(x) for x in value]

    def _formatted_many2many(self, record, field, value):
        return self._formatted_one2many(record, field, value)

    def _formatted_boolean(self, record, field, value):
        return (gettext('html_report.msg_yes') if value else
            gettext('html_report.msg_no'))

    def _formatted_date(self, record, field, value):
        if value is None:
            return ''
        return self._get_lang().strftime(value)

    def _formatted_datetime(self, record, field, value):
        if value is None:
            return ''
        return self._get_lang().strftime(value)

    def _formatted_timestamp(self, record, field, value):
        return self._formatted_datetime(record, field, value)

    def _formatted_timedelta(self, record, field, value):
        if value is None:
            return ''
        return strfdelta(value, '{hours}:{minutes}')

    def _formatted_char(self, record, field, value):
        if value is None:
            return ''
        Model = Pool().get(record.__name__)
        value = getattr(Model(record.id), field.name)
        return value.replace('\n', '<br/>')

    def _formatted_text(self, record, field, value):
        return self._formatted_char(record, field, value)

    def _formatted_integer(self, record, field, value):
        if value is None:
            return ''
        return str(value)

    def _formatted_float(self, record, field, value, grouping=True, monetary=None):
        if value is None:
            return ''
        digits = field.digits
        if isinstance(digits, str):
            digits = getattr(record, digits).digits if getattr(record, digits) else None
        else:
            # TODO remove from issue10677
            if digits:
                digits = digits[1]
        if not isinstance(digits, int):
            digits = _record_eval_pyson(record, digits,
                encoded=False)
        if digits is None:
            d = value
            if not isinstance(d, Decimal):
                d = Decimal(repr(value))
            digits = -int(d.as_tuple().exponent)
        return self._get_lang().format('%.' + str(digits) + 'f', value,
            grouping=grouping, monetary=monetary)

    def _formatted_numeric(self, record, field, value):
        return self._formatted_float(record, field, value)

    def _formatted_binary(self, record, field, value):
        if not value:
            return
        value = binascii.b2a_base64(value)
        value = value.decode('ascii')
        filename = field.filename
        mimetype = None
        if filename:
            mimetype = mimetypes.guess_type(filename)[0]
        if not mimetype:
            mimetype = DEFAULT_MIME_TYPE
        return ('data:%s;base64,%s' % (mimetype, value)).strip()

    def _formatted_selection(self, record, field, value):
        if value is None:
            return ''

        Model = Pool().get(record.__name__)
        record = Model(record.id)
        t  = TranslatedSelection(field.name)
        return t.__get__(record, record).replace('\n', '<br/>')

    # TODO: Implement: dict, multiselection


class FormattedRecord:
    def __init__(self, record, formatter=None):
        self._raw_record = record
        if formatter:
            self.__formatter = formatter
        else:
            self.__formatter = Formatter()

    def __getattr__(self, name):
        value = getattr(self._raw_record, name)
        field = self._raw_record._fields.get(name)
        if not field:
            return value
        return self.__formatter.format(self._raw_record, field, value)


class DualRecord:
    def __init__(self, record, formatter=None):
        self.raw = record
        self._formatter = formatter
        if not self._formatter:
            self._formatter = Formatter()
        self.render = FormattedRecord(record, self._formatter)

    def __bool__(self):
        return bool(self.raw)

    def __getattr__(self, name):
        field = self.raw._fields.get(name)
        if not field:
            raise DualRecordError('Field "%s" not found in record of model '
                '"%s".' % (name, self.raw.__name__))
        if field._type not in {'many2one', 'one2one', 'reference', 'one2many',
                'many2many'}:
            raise DualRecordError('You are trying to access field "%s" of type '
                '"%s" in a DualRecord of model "%s". You must use "raw." or '
                '"render." before the field name.' % (name, field._type,
                    self.raw.__name__))
        value = getattr(self.raw, name)
        if not value:
            return value
        if field._type in {'many2one', 'one2one', 'reference'}:
            return DualRecord(value, self._formatter)
        return [DualRecord(x, self._formatter) for x in value]

    @property
    def _attachments(self):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        return [DualRecord(x, self._formatter) for x in
            Attachment.search([('resource', '=', str(self.raw))])]

    @property
    def _notes(self):
        pool = Pool()
        Note = pool.get('ir.note')
        return [DualRecord(x, self._formatter) for x in
            Note.search([('resource', '=', str(self.raw))])]

    def refresh(self):
        'Re-instantiates the object using the current context. '
        'This can be useful if the DualRecord instance was outside '
        'the {% language %} tag.'
        self.raw = self.raw.__class__(self.raw.id)
        self.render = FormattedRecord(self.raw, self._formatter)

    def __lt__(self, other):
        raw = getattr(other, 'raw', other)
        if not (hasattr(raw, '__name__') and hasattr(raw, 'id')):
            return NotImplemented
        return ((self.raw.__name__, self.raw.id)
            < (raw.__name__, raw.id))

    def __eq__(self, other):
        if isinstance(other, DualRecord):
            return (self.raw.__name__ == other.raw.__name__
                and self.raw.id == other.raw.id)
        raw = getattr(other, 'raw', other)
        if hasattr(raw, '__name__') and hasattr(raw, 'id'):
            return self.raw.__name__ == raw.__name__ and self.raw.id == raw.id
        return False

    def __hash__(self):
        return hash((self.raw.__name__, self.raw.id))


class HTMLReportMixin:
    __slots__ = ()
    babel_domain = 'messages'
    side_margin = 1
    extra_vertical_margin = 30

    @classmethod
    def get_side_margin(cls, action):
        if action and action.html_side_margin is not None:
            return action.html_side_margin
        return cls.side_margin or 0

    @classmethod
    def _get_dual_records(cls, ids, model, data):
        records = cls._get_records(ids, model, data)
        return [DualRecord(x) for x in records]

    @classmethod
    def merge_pdfs(cls, pdfs_data):
        merger = PdfWriter()
        for pdf_data in pdfs_data:
            tmppdf = BytesIO(pdf_data)
            merger.append(PdfReader(tmppdf))
            tmppdf.close()

        if COMPACT_ON_MERGE:
            # Use ghostscript to compact PDF which will usually remove
            # duplicated images. It can make a PDF go from 17MB to 1.8MB,
            # for example.
            path = tempfile.mkdtemp()
            merged_path = os.path.join(path, 'merged.pdf')
            merged = open(merged_path, 'wb')
            merger.write(merged)
            merged.close()

            compacted_path = os.path.join(path, 'compacted.pdf')
            # changed PDFSETTINGS from /printer to /prepress
            command = ['gs', '-q', '-dBATCH', '-dNOPAUSE', '-dSAFER',
                '-sDEVICE=pdfwrite', '-dPDFSETTINGS=/prepress',
                '-sOutputFile=%s' % compacted_path, merged_path]
            subprocess.call(command)

            f = open(compacted_path, 'r')
            try:
                pdf_data = f.read()
            finally:
                f.close()
        else:
            tmppdf = BytesIO()
            merger.write(tmppdf)
            pdf_data = tmppdf.getvalue()
            merger.close()
            tmppdf.close()

        return pdf_data

    @classmethod
    def get_action(cls, data):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')

        action_id = data.get('action_id')
        if action_id is None:
            action_reports = ActionReport.search([
                    ('report_name', '=', cls.__name__)
                    ])
            assert action_reports, '%s not found' % cls
            action = action_reports[0]
        else:
            action = ActionReport(action_id)

        return action, action.model or data.get('model')

    @classmethod
    def get_name(cls, action):
        return action.name

    @classmethod
    def get_direct_print(cls, action):
        return action.direct_print

    @classmethod
    def get_template_filters(cls):
        """
        Returns filters that are made available in the template context.
        By default, the following filters are available:

        * render: Renders value depending on its type
        * modulepath: Returns the absolute path of a file inside a
            tryton-module (e.g. sale/sale.css)

        For additional arguments that can be passed to these filters,
        refer to the Babel `Documentation
        <http://babel.edgewall.org/wiki/Documentation>`_.
        """
        Lang = Pool().get('ir.lang')

        def module_path(name):
            module, path = name.split('/', 1)
            try:
                with file_open(os.path.join(module, path)) as f:
                    return 'file://' + f.name
            except FileNotFoundError:
                pass

        def base64(name):
            module, path = name.split('/', 1)
            with file_open(os.path.join(module, path), 'rb') as f:
                value = binascii.b2a_base64(f.read())
                value = value.decode('ascii')
                mimetype = mimetypes.guess_type(f.name)[0]
                if not mimetype:
                    mimetype = DEFAULT_MIME_TYPE
                return ('data:%s;base64,%s' % (mimetype, value)).strip()

        def nullslast(tuple_list):
            if not isinstance(tuple_list, list):
                raise UserError(gettext(
                    'html_report.nullslat_incorrect_format'))
            if not all(isinstance(t, tuple) for t in tuple_list):
                raise UserError(gettext(
                    'html_report.nullslat_incorrect_format'))
            none_elements = []
            non_none_elements = []
            for t in tuple_list:
                if t[0]:
                    non_none_elements.append(t)
                else:
                    none_elements.append(t)
            return non_none_elements + none_elements

        def short_url(value):
            pattern = r"""(?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.]/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.]\b/?(?!@)))"""
            find_urls = re.findall(pattern, value)

            for furl in find_urls:
                netloc = urlparse(furl).netloc
                if netloc:
                    r = (furl, '<a href="%s">%s</a>' % (furl, netloc))
                    value = value.replace(*r)
            return value

        locale = Transaction().context.get('report_lang',
            Transaction().language).split('_')[0]
        langs = Lang.search([
                ('code', '=', locale or 'en'),
                ], limit=1)
        lang = langs[0] if langs else 'en'
        return {
            'base64': base64,
            'currencyformat': partial(numbers.format_currency, locale=locale),
            'decimalformat': partial(numbers.format_decimal, locale=locale),
            'dateformat': partial(dates.format_date, locale=locale),
            'datetimeformat': partial(dates.format_datetime, locale=locale),
            'integer_to_words': words.integer_to_words,
            'format_currency': Report.format_currency,
            'format_date': Report.format_date,
            'format_datetime': Report.format_datetime,
            'format_number': Report.format_number,
            'format_timedelta': Report.format_timedelta,
            'grouped_slice': grouped_slice,
            'js_plus_js': tools.js_plus_js,
            'js_to_html': partial(tools.js_to_html, url_prefix='base64'),
            'js_to_text': tools.js_to_text,
            'modulepath': module_path,
            'nullslast': nullslast,
            'numberformat': partial(numbers.format_number, locale=locale),
            'number_to_words': words.number_to_words,
            'render': partial(render, lang=lang),
            'percentformat': partial(numbers.format_percent, locale=locale),
            'scientificformat': partial(
                numbers.format_scientific, locale=locale),
            'short_url': short_url,
            'timedeltaformat': partial(dates.format_timedelta, locale=locale),
            'timeformat': partial(dates.format_time, locale=locale),
            }

    @classmethod
    def label(cls, model, field=None, lang=None):
        return tools_label(model, field=field, lang=lang)

    @classmethod
    def message(cls, message_id, *args, **variables):
        return gettext(message_id, *args, **variables)

    @classmethod
    def markdown(cls, value):
        return markdown.markdown(
            value, extensions=['fenced_code', 'tables', 'sane_lists'])

    @classmethod
    def render_jinja(cls, template_string, **context):
        # Render a small Jinja2 template string using the provided context.
        return jinja2.Template(template_string).render(**context)

    @classmethod
    def qrcode(cls, value, error_correction=qrcode.ERROR_CORRECT_M):
        # Using ERROR_CORRECT_M as default because AEAT requirement
        qr_code = qrcode.make(value, image_factory=qrcode.image.svg.SvgImage,
                    error_correction=error_correction)
        stream = io.BytesIO()
        qr_code.save(stream=stream)
        return cls.to_base64(stream.getvalue())

    @classmethod
    def barcode(cls, name, code, size=(), **kwargs):
        # For the list of available options see:
        # https://python-barcode.readthedocs.io/en/latest/writers.html
        # Override Report.barcode() to return a data URI string because
        # html_report uses the result directly as the src of img tags.
        ean_class = barcode.get_barcode_class(name)
        image = ean_class(code, writer=SVGWriter()).render(kwargs)
        return cls.to_base64(image)

    @classmethod
    def datamatrix(cls, value):
        matrix = DataMatrix(value)
        return cls.to_base64(bytes(matrix.svg(), 'utf-8'))

    @staticmethod
    def to_base64(value):
        value = binascii.b2a_base64(value)
        value = value.decode('ascii')
        mimetype = "image/svg+xml"
        return ('data:%s;base64,%s' % (mimetype, value)).strip()

    @classmethod
    def dualrecord(cls, record):
        if not record:
            return
        if isinstance(record, str):
            model, id = record.split(',')
            record = Pool().get(model)(id)
        return DualRecord(record)

    @classmethod
    def weasyprint_render(cls, content):
        return weasyprint.HTML(string=content, media_type=MEDIA_TYPE).render()
