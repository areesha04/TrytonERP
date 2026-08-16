# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval
from trytond.cache import Cache
from trytond.ir.lang import get_parent_language


class ActionReport(metaclass=PoolMeta):
    __name__ = 'ir.action.report'
    html_zipped = fields.Boolean('Zipped', states={
        'invisible': ~Eval('single'),
        },
        help='If set, a zip file with a document per record will be created.')
    html_copies = fields.Integer('Number of copies')
    html_side_margin = fields.Float('Side Margin (cm)')
    html_extra_vertical_margin = fields.Integer('Extra Vertical Margin (cm)')
    html_file_name = fields.Char('Report File Name Pattern', translate=True,
        help='By default, the file name is generated from the report name and '
        'the record’s full name. To customize the file name, define a '
        'Jinja2 pattern. The record is evaluated as a DualRecord, so fields '
        'must be accessed through raw or render. Example: '
        'demo-{{ record.render.rec_name }}')

    @classmethod
    def view_attributes(cls):
        return super(ActionReport, cls).view_attributes() + [
            ('//page[@id="html_report"]', 'states', {
                    'invisible': Eval('template_extension') != 'html',
                    })]

    @classmethod
    def gettext(cls, *args, **variables):
        HTMLTemplateTranslation = Pool().get('html.template.translation')

        report, src, lang = args
        translations = HTMLTemplateTranslation.search([
            ('report', '=', report),
            ('src', '=', src),
            ('lang', '=', lang),
            ], limit=1)
        if translations:
            translation, = translations
            text = translation.value or translation.src
        else:
            parent_lang = get_parent_language(lang)
            translations = HTMLTemplateTranslation.search([
                ('report', '=', report),
                ('src', '=', src),
                ('lang', '=', parent_lang),
                ], limit=1)
            if translations:
                translation, = translations
                text = translation.value or translation.src
            else:
                text = src
        return text if not variables else text % variables


class HTMLTemplateTranslation(ModelSQL, ModelView):
    'HTML Template Translation'
    __name__ = 'html.template.translation'
    _order_name = 'src'
    report = fields.Many2One('ir.action.report', 'Report', required=True,
        ondelete='CASCADE')
    src = fields.Text('Source', required=True)
    value = fields.Text('Translation Value')
    lang = fields.Selection('get_language', string='Language', required=True)
    _get_language_cache = Cache('html.template.translation.get_language')

    @classmethod
    def get_language(cls):
        result = cls._get_language_cache.get(None)
        if result is not None:
            return result
        pool = Pool()
        Lang = pool.get('ir.lang')
        langs = Lang.search([])
        result = [(lang.code, lang.name) for lang in langs]
        cls._get_language_cache.set(None, result)
        return result

    @property
    def unique_key(self):
        return (self.src, self.lang)
