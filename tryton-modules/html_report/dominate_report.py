from io import BytesIO
import zipfile

from dominate import document
from dominate.util import raw
from dominate.tags import b, br, div, meta, span, strong, style, table, td, th, tr

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView
from trytond.tools import slugify
from trytond.transaction import Transaction

from .engine import HTMLReportMixin, DualRecord
from .generator import PdfGenerator
from trytond.tools import file_open
from .tools import label


class DominateCommon(ModelView):
    __name__ = 'html_report.dominate.common'

    @classmethod
    def css(cls, action, data, records):
        with file_open('html_report/base.css') as f:
            return f.read()


class DominateCommonCompany(metaclass=PoolMeta):
    __name__ = 'html_report.dominate.common'

    @classmethod
    def show_company_info(cls, company, show_party=True,
            show_contact_mechanism=True, show_phone=True,
            show_email=True, show_website=True):
        if not company or not getattr(company, 'raw', None):
            return raw('')
        party = company.party
        address = party.addresses and party.addresses[0] or None
        tax_identifier = party.tax_identifier

        container = div(id='company-info', cls='header-details')
        if show_party:
            with container:
                span(company.party.render.name, cls='company-info-name')
                br()
        if tax_identifier:
            with container:
                raw(tax_identifier.render.code)
                br()
        if address:
            with container:
                with div(cls='company-info-address'):
                    raw(address.render.full_address.replace('\n', '<br/>'))
        if show_contact_mechanism:
            with container:
                with div(cls='company-info-contact-mechanims'):
                    if show_phone and party.raw.phone:
                        raw('%s: %s' % (
                            label('party.party', 'phone'),
                            party.render.phone))
                        br()
                    if show_email and party.raw.email:
                        raw(party.render.email)
                        br()
                    if show_website and party.raw.website:
                        raw(party.render.website)
        return container

    @classmethod
    def show_footer(cls, company=None):
        return raw('<p align="center"> </p>')

    @classmethod
    def show_totals(cls, record):
        if not record:
            return raw('')
        totals_table = table(id='totals')
        with totals_table:
            with tr():
                th('%s:' % label(record.raw.__name__,
                    'untaxed_amount'), scope='row',
                    cls='text-right total-label total-luntaxed')
                td('%s %s' % (record.render.untaxed_amount,
                    record.currency.render.symbol),
                    cls='text-right total-value total-vuntaxed')
            with tr():
                th('%s:' % label(record.raw.__name__,
                    'tax_amount'), scope='row',
                    cls='text-right total-label total-ltax')
                td('%s %s' % (record.render.tax_amount,
                    record.currency.render.symbol),
                    cls='text-right total-value total-vtax')
            with tr():
                th('%s:' % label(record.raw.__name__,
                    'total_amount'), scope='row',
                    cls='text-right total-label total-lamount')
                td('%s %s' % (record.render.total_amount,
                    record.currency.render.symbol),
                    cls='text-right total-value total-vamount')
        return totals_table

    @classmethod
    def show_payment_info(cls, document):
        if not document:
            return raw('')
        container = div()
        with container:
            if getattr(document.raw, 'payment_term', None):
                strong('%s: ' % label(
                    document.raw.__name__, 'payment_term'))
                raw(document.payment_term.render.name)
                br()
            if getattr(document.raw, 'payment_type', None):
                strong('%s: ' % label(
                    document.raw.__name__, 'payment_type'))
                raw(document.payment_type.render.name)
                br()
            if getattr(document.raw, 'bank_account', None):
                strong('%s: ' % label(
                    document.raw.__name__, 'bank_account'))
                raw(document.bank_account.render.rec_name)
                if (document.bank_account.bank
                        and document.bank_account.bank.raw.bic):
                    raw(' (%s)' % document.bank_account.bank.render.bic)
                br()
            strong('%s:' % label(
                document.raw.__name__, 'currency'))
            raw(' %s' % document.currency.render.name)
            if getattr(document.raw, 'different_currencies', None):
                strong('%s:' % label(
                    document.raw.__name__, 'currency'))
                raw(' %s' % document.company.currency.render.name)
                strong('%s:' % label(
                    document.raw.__name__, 'company_untaxed_amount'))
                raw(' %s' % document.render.company_untaxed_amount)
                strong('%s:' % label(
                    document.raw.__name__, 'company_tax_amount'))
                raw(' %s' % document.render.company_tax_amount)
                strong('%s:' % label(
                    document.raw.__name__, 'company_total_amount'))
                raw(' %s' % document.render.company_total_amount)
        return container


class DominateCommonParty(metaclass=PoolMeta):
    __name__ = 'html_report.dominate.common'

    @classmethod
    def show_party_info(cls, party, tax_identifier, address,
            second_address_label, second_address, show_phone=True,
            show_email=True, show_website=True):
        if not party or not getattr(party, 'raw', None):
            return raw('')
        record = DualRecord(party.raw)
        container = div()
        with container:
            b(record.render.name)
            br()
            if tax_identifier:
                raw(tax_identifier.render.code)
                br()
            if address:
                raw(address.render.full_address.replace('\n', '<br/>'))
            br()
            if show_phone and record.raw.phone:
                raw('%s: %s' % (
                    HTMLReportMixin.label('party.party', 'phone'),
                    record.render.phone))
                br()
            if show_email and record.raw.email:
                raw(record.render.email)
                br()
            if second_address and address and second_address.raw.id != address.raw.id:
                if second_address_label:
                    strong(' %s' % second_address_label)
                    br()
                raw(second_address.render.full_address.replace('\n', '<br/>'))
        return container


class DominateReport(HTMLReportMixin, metaclass=PoolMeta):
    _single = False
    _header_margin_template = (
        'header#header { '
        'left: %(side_margin)scm; '
        'right: %(side_margin)scm; '
        'margin-left: 0cm; '
        'margin-right: 0cm; '
        'width: auto; }\n')
    _body_margin_template = (
        'body { '
        'left: %(side_margin)scm; '
        'right: %(side_margin)scm; '
        'margin-left: 0cm; '
        'margin-right: 0cm; '
        'width: auto; }\n')
    _footer_margin_template = (
        'footer#footer { '
        'margin-left: %(side_margin)scm; '
        'margin-right: %(side_margin)scm; '
        'width: auto; }\n')
    _last_footer_margin_template = (
        'body { '
        'margin-left: %(side_margin)scm; '
        'margin-right: %(side_margin)scm; '
        'width: auto; }\n')

    @classmethod
    def body(cls, action, data, records):
        raise NotImplementedError

    @classmethod
    def title(cls, action, data, records):
        if records and len(records) == 1:
            record, = records
            return '%s %s' % (
                cls.label(record.raw.__name__), record.render.rec_name)
        if action and action.model:
            return cls.label(action.model)
        return action.name if action else ''

    @classmethod
    def body_wrapper(cls, action, data, records):
        body_nodes = cls.body(action, data, records)
        title = cls.title(action, data, records)
        if body_nodes is None:
            body_nodes = []
        if not isinstance(body_nodes, (list, tuple)):
            body_nodes = [body_nodes]
        return cls.build_document(action, data, records, title, body_nodes)

    @classmethod
    def header(cls, action, data, records):
        return None

    @classmethod
    def footer(cls, action, data, records):
        return None

    @classmethod
    def last_footer(cls, action, data, records):
        return None

    @classmethod
    def header_wrapper(cls, action, data, records):
        return cls._wrap_with_css(
            cls.css_header(action, data, records),
            cls.header(action, data, records))

    @classmethod
    def footer_wrapper(cls, action, data, records):
        return cls._wrap_with_css(
            cls.css_footer(action, data, records),
            cls.footer(action, data, records))

    @classmethod
    def last_footer_wrapper(cls, action, data, records):
        return cls._wrap_with_css(
            cls.css_last_footer(action, data, records),
            cls.last_footer(action, data, records))

    @classmethod
    def _render_node(cls, node):
        if node is None:
            return None
        return node.render() if hasattr(node, 'render') else str(node)

    @classmethod
    def common(cls):
        return Pool().get('html_report.dominate.common')

    @classmethod
    def css(cls, action, data, records):
        return cls.common().css(action, data, records)

    @classmethod
    def css_body(cls, action, data, records):
        css = cls.css(action, data, records) or ''
        side_margin = cls.get_side_margin(action)
        return '%s\n%s' % (
            css,
            cls._body_margin_template % {'side_margin': side_margin})

    @classmethod
    def css_header(cls, action, data, records):
        css = cls.css(action, data, records) or ''
        side_margin = cls.get_side_margin(action)
        return '%s\n%s' % (
            css,
            cls._header_margin_template % {'side_margin': side_margin})

    @classmethod
    def css_footer(cls, action, data, records):
        css = cls.css(action, data, records) or ''
        side_margin = cls.get_side_margin(action)
        return '%s\n%s' % (
            css,
            cls._footer_margin_template % {'side_margin': side_margin})

    @classmethod
    def css_last_footer(cls, action, data, records):
        css = cls.css(action, data, records) or ''
        side_margin = cls.get_side_margin(action)
        return '%s\n%s' % (
            css,
            cls._last_footer_margin_template % {'side_margin': side_margin})

    @classmethod
    def _wrap_with_css(cls, css, node):
        if node is None:
            return None
        nodes = node if isinstance(node, (list, tuple)) else [node]
        doc = document(title='')
        with doc.head:
            if css:
                style(raw(css))
        with doc:
            for item in nodes:
                if item is None:
                    continue
                if isinstance(item, str):
                    doc.body.add(raw(item))
                else:
                    doc.body.add(item)
        return doc

    @classmethod
    def build_document(cls, action, data, records, title, body_nodes):
        doc = document(title=title)
        doc['lang'] = 'en'
        with doc.head:
            meta(charset='utf-8')
            meta(name='description', content='')
            meta(name='author', content='Nantic')
            css = cls.css_body(action, data, records)
            if css:
                style(raw(css))
        with doc:
            doc.body['id'] = 'base'
            doc.body['class'] = 'main-report'
            for node in body_nodes:
                if node is None:
                    continue
                if isinstance(node, str):
                    doc.body.add(raw(node))
                else:
                    doc.body.add(node)
        return doc

    @classmethod
    def language(cls, records):
        return Transaction().language or 'en'

    @classmethod
    def _refresh_records(cls, records):
        for record in records:
            if isinstance(record, DualRecord):
                record.refresh()

    @classmethod
    def _execute_dominate_report(cls, records, data, action, side_margin=2,
            extra_vertical_margin=30):
        extension = data.get('output_format', action.extension or 'pdf')
        render_single = action.single or cls._single
        if render_single:
            documents = []
            for record in records:
                language = cls.language([record])
                Lang = Pool().get('ir.lang')
                langs = Lang.search([('code', '=', language)], limit=1)
                lang = langs[0] if langs else 'en'
                with Transaction().set_context(
                        language=language,
                        html_report_language=lang):
                    cls._refresh_records([record])
                    content = cls._render_node(cls.body_wrapper(
                        action, data, [record]))
                    header = cls._render_node(cls.header_wrapper(
                        action, data, [record]))
                    footer = cls._render_node(cls.footer_wrapper(
                        action, data, [record]))
                    last_footer = cls._render_node(cls.last_footer_wrapper(
                        action, data, [record]))

                if extension == 'pdf':
                    documents.append(PdfGenerator(
                        content,
                        header_html=header,
                        footer_html=footer,
                        last_footer_html=last_footer,
                        side_margin=side_margin,
                        extra_vertical_margin=extra_vertical_margin,
                    ).render_pdf())
                else:
                    documents.append(content)
            if extension == 'pdf' and documents:
                if len(documents) == 1:
                    document = documents[0]
                else:
                    document = cls.merge_pdfs(documents)
            else:
                document = ''.join(documents)
        else:
            language = cls.language(records)
            Lang = Pool().get('ir.lang')
            langs = Lang.search([('code', '=', language)], limit=1)
            lang = langs[0] if langs else 'en'
            with Transaction().set_context(
                    language=language,
                    html_report_language=lang):
                cls._refresh_records(records)
                content = cls._render_node(cls.body_wrapper(
                    action, data, records))
                header = cls._render_node(cls.header_wrapper(
                    action, data, records))
                footer = cls._render_node(cls.footer_wrapper(
                    action, data, records))
                last_footer = cls._render_node(cls.last_footer_wrapper(
                    action, data, records))
            if extension == 'pdf':
                document = PdfGenerator(
                    content,
                    header_html=header,
                    footer_html=footer,
                    last_footer_html=last_footer,
                    side_margin=side_margin,
                    extra_vertical_margin=extra_vertical_margin,
                ).render_pdf()
            else:
                document = content

        if extension == 'xlsx':
            from bs4 import BeautifulSoup
            from openpyxl import Workbook
            from .tools import save_virtual_workbook, _convert_str_to_float

            wb = Workbook()
            ws = wb.active

            soup = BeautifulSoup(document, 'html.parser')
            for table_node in soup.find_all('table'):
                for row in table_node.find_all('tr'):
                    row_data = []
                    for cell in row.find_all(['td', 'th']):
                        row_data.append(_convert_str_to_float(cell.text))
                    ws.append(row_data)
                document = save_virtual_workbook(wb)
        return extension, document

    @classmethod
    def execute(cls, ids, data):
        action, model = cls.get_action(data)
        cls.check_access(action, model, ids)

        if action.template_extension != 'html':
            return super().execute(ids, data)

        action_name = cls.get_name(action)
        side_margin = action.html_side_margin
        if side_margin is None:
            side_margin = cls.side_margin
        extra_vertical_margin = action.html_extra_vertical_margin
        if extra_vertical_margin is None:
            extra_vertical_margin = cls.extra_vertical_margin

        if Transaction().context.get('output_format') == 'html':
            is_zip, is_merge_pdf, Printer = None, None, None
            output_format = data['output_format'] = 'html'
        else:
            is_zip = action.single and len(ids) > 1 and action.html_zipped
            is_merge_pdf = action.html_copies and action.html_copies > 1
            Printer = None
            try:
                Printer = Pool().get('printer')
            except KeyError:
                pass
            output_format = data.get('output_format', action.extension or 'pdf')

        data['html_dual_record'] = True
        records = []
        with Transaction().set_context(
                html_report=action.id,
                address_with_party=False,
                output_format=output_format):
            if model and ids:
                records = cls._get_dual_records(ids, model, data)

                if action.html_file_name:
                    filename = slugify('-'.join(
                            cls.render_jinja(
                                action.html_file_name, record=record)
                            for record in records[:5]))
                else:
                    suffix = '-'.join(r.render.rec_name for r in records[:5])
                    if len(records) > 5:
                        suffix += '__' + str(len(records[5:]))
                    filename = slugify('%s-%s' % (action_name, suffix))
            else:
                records = []
                filename = slugify(action_name)

            if is_zip:
                content = BytesIO()
                with zipfile.ZipFile(content, 'w') as content_zip:
                    for record in records:
                        oext, rcontent = cls._execute_dominate_report(
                            [record],
                            data,
                            action,
                            side_margin=side_margin,
                            extra_vertical_margin=extra_vertical_margin)
                        rfilename = '%s.%s' % (
                            slugify(record.render.rec_name),
                            oext)
                        if action.html_copies and action.html_copies > 1:
                            rcontent = cls.merge_pdfs(
                                [rcontent] * action.html_copies)
                        content_zip.writestr(rfilename, rcontent)
                content = content.getvalue()
                return ('zip', content, False, filename)

            oext, content = cls._execute_dominate_report(
                records,
                data,
                action,
                side_margin=side_margin,
                extra_vertical_margin=extra_vertical_margin)
            if content is None:
                content = ''
            if not isinstance(content, str):
                content = bytes(content)

            if is_merge_pdf:
                content = cls.merge_pdfs([content] * action.html_copies)
            if Printer:
                return Printer.send_report(oext, content,
                    action_name, action)
            return oext, content, cls.get_direct_print(action), filename
