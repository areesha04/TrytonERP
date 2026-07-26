import datetime as dt
import unittest
from decimal import Decimal

from proteus import Model, Report, Wizard
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def _create_product(self, name, code, cost_price, unit):
        ProductTemplate = Model.get('product.template')

        template = ProductTemplate()
        template.name = name
        template.code = code
        template.default_uom = unit
        template.type = 'goods'
        template.list_price = Decimal('20')
        template.cost_price_method = 'fixed'
        template.save()
        product, = template.products
        product.cost_price = cost_price
        product.save()
        return product

    def _fill_storage(self, supplier_loc, storage_loc, currency, moves_data):
        StockMove = Model.get('stock.move')
        today = dt.date.today()

        moves = []
        for product, quantity, unit_price in moves_data:
            move = StockMove()
            move.product = product
            move.unit = product.default_uom
            move.quantity = quantity
            move.from_location = supplier_loc
            move.to_location = storage_loc
            move.planned_date = today
            move.effective_date = today
            move.unit_price = unit_price
            move.currency = currency
            moves.append(move)
        StockMove.click(moves, 'do')

    def _create_inventory(self, storage_loc, quantities_by_product):
        Inventory = Model.get('stock.inventory')

        inventory = Inventory()
        inventory.location = storage_loc
        inventory.empty_quantity = 'keep'
        inventory.save()
        inventory.click('complete_lines')
        lines = {line.product.id: line for line in inventory.lines}
        for product, quantity in quantities_by_product:
            lines[product.id].quantity = quantity
        inventory.save()
        inventory.click('confirm')
        return inventory

    def _run_total_inventory_wizard(self, warehouse, products, output_format):
        Product = Model.get('product.product')
        Location = Model.get('stock.location')

        wizard = Wizard('html_report.stock.print_total_inventory')
        wizard.form.locations.append(Location(warehouse.id))
        for product in products:
            wizard.form.products.append(Product(product.id))
        wizard.form.quantities = 'positive'
        wizard.form.order = 'location'
        wizard.form.output_format = output_format
        wizard.form.timeout = 120
        wizard.execute('print_')
        self.assertEqual(len(wizard.actions), 1)
        return wizard.actions[0]

    def test(self):
        activate_modules(['html_report', 'stock_valued'])

        _ = create_company()
        _ = get_company()
        currency = get_currency()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])

        product1 = self._create_product(
            'Product 1', 'P1', Decimal('5'), unit)
        product2 = self._create_product(
            'Product 2', 'P2', Decimal('7'), unit)

        Location = Model.get('stock.location')
        warehouse, = Location.find([('code', '=', 'WH')])
        storage_loc, = Location.find([('code', '=', 'STO')])
        supplier_loc, = Location.find([('code', '=', 'SUP')])

        self._fill_storage(supplier_loc, storage_loc, currency, [
                (product1, 5, Decimal('5')),
                (product2, 3, Decimal('7')),
                ])

        inventory = self._create_inventory(storage_loc, [
                (product1, 4),
                (product2, 3),
                ])

        InventoryReport = Report('stock.inventory')
        oext, _, _, _ = InventoryReport.execute([inventory])
        self.assertEqual(oext, 'pdf')

        BlindInventoryReport = Report('stock.inventory.blind')
        oext, _, _, _ = BlindInventoryReport.execute([inventory])
        self.assertEqual(oext, 'pdf')

        InventoryValuedReport = Report('stock.inventory.valued')
        oext, _, _, _ = InventoryValuedReport.execute([product1, product2])
        self.assertEqual(oext, 'pdf')

        LocationInventoryValuedReport = Report('stock.location.inventory.valued')
        oext, _, _, _ = LocationInventoryValuedReport.execute([warehouse])
        self.assertEqual(oext, 'pdf')

        oext, content, _, _ = self._run_total_inventory_wizard(
            warehouse, [product1, product2], 'pdf')
        self.assertEqual(oext, 'pdf')
        self.assertTrue(isinstance(content, bytes))

        oext, content, _, _ = self._run_total_inventory_wizard(
            warehouse, [product1, product2], 'html')
        self.assertEqual(oext, 'html')
        self.assertTrue(isinstance(content, str))
        self.assertIn('Total Inventory', content)

        oext, content, _, _ = self._run_total_inventory_wizard(
            warehouse, [product1, product2], 'xlsx')
        self.assertEqual(oext, 'xlsx')
        self.assertTrue(isinstance(content, bytes))
        self.assertTrue(content.startswith(b'PK'))
