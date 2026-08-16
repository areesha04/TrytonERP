from lxml import etree

from trytond.pool import PoolMeta


class _WidgetValidator:
    def __init__(self, validator, widgets):
        self._validator = validator
        self._widgets = widgets

    def _prepare_tree(self, tree):
        if not self._widgets:
            return tree
        tree = etree.fromstring(etree.tostring(tree))
        widgets = ' or '.join(f'@widget="{widget}"' for widget in self._widgets)
        for field in tree.xpath(f'.//field[{widgets}]'):
            field.set('widget', 'text')
            field.attrib.pop('language', None)
        return tree

    def validate(self, tree):
        return self._validator.validate(self._prepare_tree(tree))

    def assertValid(self, tree):
        return self._validator.assertValid(self._prepare_tree(tree))

    @property
    def error_log(self):
        return self._validator.error_log


class View(metaclass=PoolMeta):
    __name__ = 'ir.ui.view'

    @classmethod
    def _validator(cls, type_):
        validator = super()._validator(type_)
        widgets = set()
        if type_ in {'form', 'list-form'}:
            widgets.update({'block', 'code'})
        if widgets and not isinstance(validator, _WidgetValidator):
            validator = _WidgetValidator(validator, widgets)
            key = (cls.__name__, type_)
            validator = cls._get_validator_cache.set(key, validator)
        return validator
