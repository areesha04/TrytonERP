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
        activate_modules(['html_report', 'purchase'])

        _ = create_company()
        company = get_company()

        Party = Model.get('party.party')
        supplier = Party(name='Supplier')
        supplier.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.purchasable = True
        template.save()
        product, = template.products

        Purchase = Model.get('purchase.purchase')
        PurchaseLine = Model.get('purchase.line')
        purchase = Purchase()
        purchase.party = supplier
        purchase.company = company
        line = PurchaseLine()
        purchase.lines.append(line)
        line.product = product
        line.quantity = 2
        line.unit_price = Decimal('10')
        purchase.click('quote')
        purchase.save()

        PurchaseReport = Report('purchase.purchase')
        oext, _, _, _ = PurchaseReport.execute([purchase])
        self.assertEqual(oext, 'pdf')
