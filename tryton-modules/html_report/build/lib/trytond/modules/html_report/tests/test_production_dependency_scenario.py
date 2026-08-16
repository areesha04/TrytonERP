import unittest
import datetime as dt
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
        activate_modules(['html_report', 'production'])

        _ = create_company()
        company = get_company()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        meter, = ProductUom.find([('name', '=', 'Meter')])
        centimeter, = ProductUom.find([('name', '=', 'Centimeter')])

        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.producible = True
        template.list_price = Decimal('30')
        product, = template.products
        product.cost_price = Decimal('20')
        template.save()
        product, = template.products

        template1 = ProductTemplate()
        template1.name = 'component 1'
        template1.default_uom = unit
        template1.type = 'goods'
        template1.list_price = Decimal('5')
        component1, = template1.products
        component1.cost_price = Decimal('1')
        template1.save()
        component1, = template1.products

        template2 = ProductTemplate()
        template2.name = 'component 2'
        template2.default_uom = meter
        template2.type = 'goods'
        template2.list_price = Decimal('7')
        component2, = template2.products
        component2.cost_price = Decimal('5')
        template2.save()
        component2, = template2.products

        BOM = Model.get('production.bom')
        BOMInput = Model.get('production.bom.input')
        BOMOutput = Model.get('production.bom.output')
        bom = BOM(name='product')
        input1 = BOMInput()
        bom.inputs.append(input1)
        input1.product = component1
        input1.quantity = 5
        input2 = BOMInput()
        bom.inputs.append(input2)
        input2.product = component2
        input2.quantity = 150
        input2.unit = centimeter
        output = BOMOutput()
        bom.outputs.append(output)
        output.product = product
        output.quantity = 1
        bom.save()

        Production = Model.get('production')
        production = Production()
        production.company = company
        production.planned_date = dt.date.today()
        production.product = product
        production.bom = bom
        production.quantity = 2
        production.save()

        ProductionReport = Report('production.production')
        oext, _, _, _ = ProductionReport.execute([production])
        self.assertEqual(oext, 'pdf')
