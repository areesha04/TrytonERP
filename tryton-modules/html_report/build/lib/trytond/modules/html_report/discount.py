from trytond.model import fields


class HTMLDiscountReportMixin:
    __slots__ = ()

    html_discount = fields.Function(fields.Char(
        "HTML Discount"), 'get_html_discount')

    def get_html_discount(self, name):
        return self.discount or ''
