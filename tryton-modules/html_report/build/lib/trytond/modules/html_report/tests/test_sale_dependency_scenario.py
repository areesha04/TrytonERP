import unittest

from decimal import Decimal

from proteus import Model, Report
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        activate_modules(['html_report', 'sale'])

        _ = create_company()
        company = get_company()

        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.salable = True
        template.save()
        product, = template.products

        Sale = Model.get('sale.sale')
        SaleLine = Model.get('sale.line')
        sale = Sale()
        sale.party = customer
        sale.company = company
        line = SaleLine()
        sale.lines.append(line)
        line.product = product
        line.quantity = 2
        line.unit_price = Decimal('10')
        line = SaleLine()
        sale.lines.append(line)
        line.type = 'comment'
        line.description = 'Comment'
        sale.click('quote')
        sale.save()

        SaleReport = Report('sale.sale')
        oext, data, _, _ = SaleReport.execute([sale])
        self.assertEqual(oext, 'pdf')
        self.assertTrue(data.startswith(b'%PDF'))

        oext, merged_data, _, _ = SaleReport.execute([sale, sale])
        self.assertEqual(oext, 'pdf')
        self.assertTrue(merged_data.startswith(b'%PDF'))
        self.assertGreater(len(merged_data), len(data))
