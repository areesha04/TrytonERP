from babel.messages import extract

from trytond.modules import get_module_info
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

INTERNAL_LANG = 'en'
KEY = 'x'
TYPE = 'xgettext'


def _(message):
    Translation = Pool().get('ir.translation')
    lang = Transaction().context.get('language', INTERNAL_LANG)
    translation = Translation.get_source(KEY, TYPE, lang, message)
    if translation is None:
        return message
    return translation


class Translation(metaclass=PoolMeta):
    __name__ = 'ir.translation'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if ('xgettext', 'XGettext') not in cls.type.selection:
            cls.type.selection.append(('xgettext', 'XGettext'))


class TranslationSet(metaclass=PoolMeta):
    __name__ = "ir.translation.set"

    def set_xgettext(self):
        pool = Pool()
        Module = pool.get('ir.module')
        Translation = pool.get('ir.translation')

        cursor = Transaction().connection.cursor()
        translation = Translation.__table__()
        for module in Module.search([('state', '=', 'activated')]):
            dependencies = {d.name for d in module.dependencies}
            if 'xgettext' not in dependencies:
                continue
            cursor.execute(*translation.select(
                    translation.src,
                    where=(translation.lang == INTERNAL_LANG)
                    & (translation.name == KEY)
                    & (translation.type == TYPE)
                    & (translation.module == module.name)))
            existing = {x[0] for x in cursor.fetchall()}

            method_map = [
                ('**.py', extract.extract_python),
                ]
            strings = set()
            module_dir = get_module_info(module.name)['directory']
            for item in extract.extract_from_dir(module_dir, method_map,
                    keywords={'_': None}):
                filename, lineno, message, comments, context = item
                strings.add(message)
                if message in existing:
                    continue
                cursor.execute(*translation.insert([
                        translation.name, translation.lang,
                        translation.type, translation.src,
                        translation.value, translation.module,
                        translation.fuzzy, translation.res_id
                        ], [[
                        KEY, INTERNAL_LANG,
                        TYPE, message,
                        '', module.name,
                        False, -1,
                        ]]))
            if strings:
                cursor.execute(*translation.delete(
                        where=(translation.name == KEY)
                        & (translation.type == TYPE)
                        & (translation.module == module.name)
                        & ~translation.src.in_(list(strings))))

    def transition_set_(self):
        self.set_xgettext()
        return super().transition_set_()


class TranslationClean(metaclass=PoolMeta):
    __name__ = 'ir.translation.clean'

    @staticmethod
    def _clean_xgettext(translation):
        return False


class TranslationUpdate(metaclass=PoolMeta):
    __name__ = 'ir.translation.update'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if TYPE not in cls._source_types:
            cls._source_types.append(TYPE)
