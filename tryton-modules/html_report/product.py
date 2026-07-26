# This file is part html_report module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.model import fields


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    html_code = fields.Function(fields.Char(
        "HTML Code"), 'get_html_code')

    def get_html_code(self, name):
        return self.code or '#%s' % self.id


class ProductCustomer(metaclass=PoolMeta):
    __name__ = 'sale.product_customer'
    notes = fields.One2Many('ir.note', 'resource', 'Notes')
