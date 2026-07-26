import unittest
import datetime as dt
from decimal import Decimal

from proteus import Model, Report
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

    def test(self):
        activate_modules(['html_report', 'stock'])

        _ = create_company()
        _ = get_company()
        currency = get_currency()

        Party = Model.get('party.party')
        customer = Party(name='Customer')
        customer.save()

        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'Product'
        template.default_uom = unit
        template.type = 'goods'
        template.list_price = Decimal('20')
        template.save()
        product, = template.products

        Location = Model.get('stock.location')
        warehouse, = Location.find([('code', '=', 'WH')])
        customer_loc, = Location.find([('code', '=', 'CUS')])
        output_loc, = Location.find([('code', '=', 'OUT')])

        ShipmentOut = Model.get('stock.shipment.out')
        StockMove = Model.get('stock.move')
        shipment = ShipmentOut()
        shipment.planned_date = dt.date.today()
        shipment.customer = customer
        shipment.warehouse = warehouse
        move = StockMove()
        shipment.outgoing_moves.append(move)
        move.product = product
        move.unit = unit
        move.quantity = 1
        move.from_location = output_loc
        move.to_location = customer_loc
        move.unit_price = Decimal('1')
        move.currency = currency
        shipment.save()

        DeliveryNote = Report('stock.shipment.out.delivery_note')
        oext, _, _, _ = DeliveryNote.execute([shipment])
        self.assertEqual(oext, 'pdf')
