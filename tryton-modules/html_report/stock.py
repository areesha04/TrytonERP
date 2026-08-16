from datetime import datetime
from tempfile import NamedTemporaryFile

from dominate.util import raw
from dominate.tags import (br, div, footer as footer_tag, h1, h2, h3, h4,
    header as header_tag, img, p, strong, table, tbody, td, th, thead, tr)
from openpyxl import Workbook

from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.report import Report
from trytond.rpc import RPC
from trytond.tools import grouped_slice
from trytond.modules.html_report.template import HTMLPartyInfoMixin
from trytond.modules.html_report.engine import DualRecord, render
from trytond.modules.html_report.tools import label
from trytond.modules.html_report.dominate_report import DominateReport
from trytond.modules.html_report.discount import HTMLDiscountReportMixin
from trytond.wizard import Wizard, StateView, StateReport, Button
from babel.dates import format_datetime
from .common import TimeoutChecker, TimeoutException
from trytond.modules.xgettext import _


class ShipmentOutReturn(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'
    show_lots = fields.Function(fields.Boolean('Show Lots'),
        'get_show_lots')

    @classmethod
    def __setup__(cls):
        super(ShipmentOutReturn, cls).__setup__()
        cls.html_party.context = {'company': Eval('company', -1)}
        cls.html_party.depends = ['company']

    def get_show_lots(self, name):
        for move in self.incoming_moves:
            if hasattr(move, 'lot') and getattr(move, 'lot'):
                return True
        return False

    def get_html_party(self, name):
        return self.customer and self.customer.id

    def get_html_second_address(self, name):
        return self.contact_address and self.contact_address.id

    def get_html_second_address_label(self, name):
        return label(self.__name__, "contact_address")


class ShipmentIn(metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'
    show_lots = fields.Function(fields.Boolean('Show Lots'),
        'get_show_lots')

    def get_show_lots(self, name):
        for move in self.moves:
            if hasattr(move, 'lot') and getattr(move, 'lot'):
                return True
        return False


class ShipmentInReturn(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.return'
    show_lots = fields.Function(fields.Boolean('Show Lots'),
        'get_show_lots')

    @classmethod
    def __setup__(cls):
        super(ShipmentInReturn, cls).__setup__()
        cls.html_party.context = {'company': Eval('company', -1)}
        cls.html_party.depends = ['company']

    def get_show_lots(self, name):
        for move in self.moves:
            if hasattr(move, 'lot') and getattr(move, 'lot'):
                return True
        return False

    def get_html_party(self, name):
        return self.supplier and self.supplier.id

    def get_html_second_address(self, name):
        return self.delivery_address and self.delivery_address.id

    def get_html_second_address_label(self, name):
        return label(self.__name__, "delivery_address")


class ShipmentOut(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'
    sorted_lines = fields.Function(fields.Many2Many('stock.move', None, None,
        'Sorted Lines'), 'get_sorted_lines')
    show_lots = fields.Function(fields.Boolean('Show Lots'),
        'get_show_lots')

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls.html_party.context = {'company': Eval('company', -1)}
        cls.html_party.depends = ['company']

    def get_html_party(self, name):
        return self.customer and self.customer.id

    def get_html_address(self, name):
        return self.delivery_address and self.delivery_address.id

    def get_html_second_address(self, name):
        return self.delivery_address and self.delivery_address.id

    def get_html_second_address_label(self, name):
        return label(self.__name__, "delivery_address")

    def get_sorted_lines(self, name):
        lines = [x for x in self.outgoing_moves]
        lines.sort(key=lambda k: k.sort_key, reverse=True)
        return [x.id for x in lines]

    @property
    def sorted_keys(self):
        keys = []
        for x in self.sorted_lines:
            if x.sort_key in keys:
                continue
            keys.append(x.sort_key)
        return keys

    def get_show_lots(self, name):
        for move in self.inventory_moves or self.outgoing_moves:
            if hasattr(move, 'lot') and getattr(move, 'lot'):
                return True
        return False


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'
    origin_key = fields.Function(fields.Char("Origin Key",
        ), 'get_origin_key')

    @property
    def sort_key(self):
        pool = Pool()
        ShipmentOut = pool.get('stock.shipment.out')
        ShipmentIn = pool.get('stock.shipment.in')

        key = []
        if self.shipment and isinstance(self.shipment, ShipmentOut):
            if self.shipment.warehouse_storage == self.shipment.warehouse_output:
                sale = (self.origin
                        and ('sale.line' in str(self.origin))
                        and self.origin.sale or None)
            else:
                sale = (self.origin
                        and ('sale.line' in str(self.origin))
                        and self.origin.sale or None)
            if sale and sale not in key:
                key.append(DualRecord(sale))

        elif self.shipment and isinstance(self.shipment, ShipmentIn):
            if self.origin and 'purchase.line' in str(self.origin):
                purchase = self.origin.purchase
                if purchase in key:
                    key.append(DualRecord(purchase))
        return key

    def get_origin_key(self, name):
        Move = Pool().get('stock.move')

        origin = self.origin
        if self.shipment and origin and isinstance(origin, Move):
            if origin.origin:
                origin = origin.origin
        if origin and hasattr(origin, 'document_origin') and origin.document_origin:
            origin = origin.document_origin
        return str(origin) if origin is not None else ''


class MoveDiscount(HTMLDiscountReportMixin, metaclass=PoolMeta):
    __name__ = 'stock.move'


class ShipmentInternal(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'
    show_lots = fields.Function(fields.Boolean('Show Lots'),
        'get_show_lots')

    @classmethod
    def __setup__(cls):
        super(ShipmentInternal, cls).__setup__()
        cls.html_party.context = {'company': Eval('company', -1)}
        cls.html_party.depends = ['company']

    def get_html_party(self, name):
        return

    def get_show_lots(self, name):
        for move in self.moves:
            if hasattr(move, 'lot') and getattr(move, 'lot'):
                return True
        return False


class StockInventory(metaclass=PoolMeta):
    __name__ = 'stock.inventory'
    show_lots = fields.Function(fields.Boolean('Show Lots'),
        'get_show_lots')

    def get_show_lots(self, name):
        for line in self.lines:
            if hasattr(line, 'lot') and getattr(line, 'lot'):
                return True
        return False


class StockReportMixin(DominateReport):

    @classmethod
    def document_title(cls, model):
        titles = {
            'stock.shipment.out': _('Customer Shipment'),
            'stock.shipment.in': _('Supplier Shipment'),
            }
        return titles.get(model, cls.label(model))

    @classmethod
    def show_carrier(cls, carrier):
        container = div()
        with container:
            raw(carrier.party.render.name)
            br()
            if carrier.party.raw.tax_identifier:
                raw(carrier.party.tax_identifier.render.code)
        return container

    @classmethod
    def show_company_info(cls, company, show_party=True,
            show_contact_mechanism=True, show_phone=True,
            show_email=True, show_website=True):
        return cls.common().show_company_info(
            company, show_party=show_party,
            show_contact_mechanism=show_contact_mechanism,
            show_phone=show_phone, show_email=show_email,
            show_website=show_website)

    @classmethod
    def show_party_info(cls, party, tax_identifier, address,
            second_address_label, second_address, show_phone=True,
            show_email=True, show_website=True):
        return cls.common().show_party_info(
            party, tax_identifier, address, second_address_label,
            second_address, show_phone=show_phone, show_email=show_email,
            show_website=show_website)

    @classmethod
    def show_footer(cls, company=None):
        return cls.common().show_footer(company)

    @classmethod
    def show_totals(cls, record):
        return cls.common().show_totals(record)

    @classmethod
    def language(cls, records):
        record = records[0] if records else None
        if record:
            if getattr(record.raw, 'customer', None):
                party = record.customer
                if party and party.raw.lang:
                    return party.raw.lang.code
            if getattr(record.raw, 'supplier', None):
                party = record.supplier
                if party and party.raw.lang:
                    return party.raw.lang.code
        return Transaction().language or 'en'

    @classmethod
    def _header_with_document_info(cls, action, data, records,
            document_info_node):
        record, = records
        company = record.company
        header = div()
        with header:
            with header_tag(id='header'):
                with table():
                    with tr():
                        with td():
                            if company.render.logo:
                                img(cls='logo', src=company.render.logo)
                        with td() as cell:
                            if document_info_node is not None:
                                cell.add(document_info_node)
                    with tr():
                        with td(cls='party_info'):
                            cls.show_company_info(company)
                        with td(cls='party_info'):
                            party = record.html_party
                            tax_identifier = record.html_tax_identifier
                            address = record.html_address
                            second_address_label = record.html_address
                            second_address = record.html_address
                            cls.show_party_info(party, tax_identifier, address,
                                second_address_label, second_address)
        return header

    @classmethod
    def _footer(cls, action, data, records):
        record, = records
        company = record.company
        footer = div()
        with footer:
            with footer_tag(id='footer', align='center'):
                cls.show_footer(company)
        return footer

    @classmethod
    def show_stock_moves(cls, document, valued=False):
        moves_table = table(style='width:100%;')
        with moves_table:
            with thead():
                with tr():
                    th(cls.label('product.product', 'code'),
                        nowrap=True)
                    th(cls.label('product.template', 'name'),
                        nowrap=True)
                    if document.raw.show_lots:
                        th(cls.label('stock.move', 'lot'))
                    th(cls.label('stock.move', 'quantity'),
                        cls='text-right', nowrap=True)
                    th(cls.label('stock.move', 'unit'),
                        nowrap=True)
                    if valued:
                        th(cls.label('stock.move', 'base_price'),
                            cls='text-right')
                        th('', cls='text-right')
                        th(cls.label('stock.move', 'amount'),
                            cls='text-right')
                    else:
                        th('', cls='hide')
                        th('', cls='hide')
                        th('', cls='hide')
            with tbody(cls='border'):
                for key in document.raw.sorted_keys:
                    if key:
                        with tr():
                            cell = th(cls='sub_header', colspan='9')
                            lines = []
                            for item in key:
                                if getattr(item.raw, 'sale_date', None):
                                    label_date = cls.label(
                                        item.raw.__name__, 'sale_date')
                                    item_date = (item.render.sale_date
                                        if getattr(item.raw, 'sale_date', None)
                                        else None)
                                else:
                                    label_date = cls.label(
                                        item.raw.__name__, 'effective_date')
                                    item_date = (item.render.effective_date
                                        if getattr(item.raw, 'effective_date',
                                            None) else None)
                                text = '%s: %s' % (
                                    cls.label(item.raw.__name__),
                                    item.render.number
                                    if getattr(item.raw, 'number', None) else '')
                                if item_date:
                                    text += f' {label_date}: {item_date}'
                                lines.append(text)
                            cell.add(raw('<br/>'.join(lines)))
                    for move in document.sorted_lines:
                        if move.raw.sort_key != key:
                            continue
                        with tr():
                            td(move.product and move.product.render.code or '-')
                            td(move.product and move.product.render.name or '-')
                            if document.raw.show_lots:
                                lot_value = ''
                                if move.lot:
                                    lot_value = move.lot.render.number
                                    if (move.raw.lot
                                            and getattr(move.lot.raw,
                                                'expiration_date', None)):
                                        lot_value += ' (%s)' % (
                                            move.lot.render.expiration_date)
                                td(lot_value)
                            td(move.render.quantity, cls='text-right')
                            td(move.unit.render.name)
                            if valued:
                                currency = (document.currency.render.symbol
                                    if document.currency else '')
                                base_price = getattr(move.raw, 'base_price',
                                    None)
                                discount = getattr(move.raw, 'discount', None)
                                amount = getattr(move.raw, 'amount', None)
                                if base_price is not None:
                                    td('%s %s' % (
                                        move.render.base_price, currency),
                                        cls='text-right', nowrap=True)
                                else:
                                    td('', cls='text-right', nowrap=True)
                                if discount:
                                    td(move.render.discount, cls='text-right',
                                        nowrap=True)
                                else:
                                    td('', cls='text-right', nowrap=True)
                                if amount is not None:
                                    td('%s %s' % (move.render.amount, currency),
                                        cls='text-right', nowrap=True)
                                else:
                                    td('', cls='text-right', nowrap=True)
                            else:
                                td('', cls='hide')
                                td('', cls='hide')
                                td('', cls='hide')
        return moves_table

    @classmethod
    def show_picking_moves(cls, moves, show_lots):
        moves_table = table(style='width:100%;')
        with moves_table:
            with thead():
                with tr():
                    th(cls.label('product.product', 'code'),
                        nowrap=True)
                    th(cls.label('product.template', 'name'),
                        nowrap=True)
                    if show_lots:
                        th(cls.label('stock.move', 'lot'))
                    th(cls.label('stock.move', 'quantity'),
                        cls='text-right', nowrap=True)
                    th(cls.label('stock.move', 'unit'),
                        nowrap=True)
            with tbody(cls='border'):
                for move in moves:
                    with tr():
                        td(move.product and move.product.render.code or '')
                        td(move.product and move.product.render.name or '-')
                        if show_lots:
                            lot_value = ''
                            if move.lot:
                                lot_value = move.lot.render.number
                                if (move.raw.lot
                                        and getattr(move.lot.raw,
                                            'expiration_date', None)):
                                    lot_value += ' (%s)' % (
                                        move.lot.render.expiration_date)
                            td(lot_value)
                        td(move.render.quantity, cls='text-right')
                        td(move.unit.render.name)
                    tr(style='border-bottom: 1px solid black;')
        return moves_table

    @classmethod
    def show_internal_picking_moves(cls, record, show_lots):
        moves = record.incoming_moves or record.moves
        moves_table = table(style='width:100%;')
        with moves_table:
            with thead():
                with tr():
                    th(cls.label('product.product', 'code'),
                        nowrap=True)
                    th(cls.label('product.template', 'name'),
                        nowrap=True)
                    if show_lots:
                        th(cls.label('stock.move', 'lot'))
                    th(cls.label('stock.move', 'quantity'),
                        cls='text-right', nowrap=True)
                    th(cls.label('stock.move', 'unit'),
                        nowrap=True)
            with tbody(cls='border'):
                for move in moves:
                    with tr():
                        td(move.product and move.product.render.code or '')
                        td(move.product and move.product.render.name or '-')
                        if show_lots:
                            lot_value = ''
                            if move.lot:
                                lot_value = move.lot.render.number
                                if (move.raw.lot
                                        and getattr(move.lot.raw,
                                            'expiration_date', None)):
                                    lot_value += ' (%s)' % (
                                        move.lot.render.expiration_date)
                            td(lot_value)
                        td(move.render.quantity, cls='text-right')
                        td(move.unit.render.name)
        return moves_table

    @classmethod
    def show_customer_return_stock_moves(cls, document, valued=False):
        show_lots = document.raw.show_lots
        show_expiration = False
        if show_lots and document.incoming_moves:
            show_expiration = bool(getattr(
                document.incoming_moves[0].raw, 'expiration_date', None))
        moves_table = table(style='width:100%;')
        with moves_table:
            with thead():
                with tr():
                    th(cls.label('product.product', 'code'),
                        nowrap=True)
                    th(cls.label('product.template', 'name'),
                        nowrap=True)
                    if show_lots:
                        th(cls.label('stock.move', 'lot'))
                        if show_expiration:
                            th(cls.label('stock.lot',
                                'expiration_date'))
                        else:
                            th('', cls='hide')
                    else:
                        th('', cls='hide')
                    th(cls.label('stock.move', 'quantity'),
                        cls='text-right', nowrap=True)
                    th(cls.label('stock.move', 'unit'),
                        nowrap=True)
                    if valued:
                        th(cls.label('stock.move', 'base_price'),
                            cls='text-right')
                        th('', cls='text-right')
                        th(cls.label('stock.move', 'amount'),
                            cls='text-right')
                    else:
                        th('', cls='hide')
                        th('', cls='hide')
                        th('', cls='hide')
            with tbody(cls='border'):
                for move in document.incoming_moves:
                    with tr():
                        td(move.product and move.product.render.code or '-')
                        td(move.product and move.product.render.name or '-')
                        if show_lots:
                            if move.lot:
                                td(move.lot.render.number)
                            else:
                                td('')
                            if move.raw.lot and getattr(
                                    move.lot.raw, 'expiration_date', None):
                                td(move.lot.render.expiration_date)
                            else:
                                td('')
                        else:
                            td('')
                        td(move.render.quantity, cls='text-right')
                        td(move.unit.render.name)
                        if valued:
                            base_price = getattr(move.raw, 'base_price', None)
                            discount = getattr(move.raw, 'discount', None)
                            amount = getattr(move.raw, 'amount', None)
                            td(move.render.base_price
                                if base_price is not None else '',
                                cls='text-right', nowrap=True)
                            if discount:
                                td(move.render.discount, cls='text-right',
                                    nowrap=True)
                            else:
                                td('', cls='text-right', nowrap=True)
                            td(move.render.amount if amount is not None else '',
                                cls='text-right', nowrap=True)
                        else:
                            td('', cls='hide')
                            td('', cls='hide')
                            td('', cls='hide')
        return moves_table

    @classmethod
    def show_return_stock_moves(cls, document, valued=False):
        show_lots = document.raw.show_lots
        show_expiration = False
        if show_lots and document.moves:
            show_expiration = bool(getattr(
                document.moves[0].raw, 'expiration_date', None))
        moves_table = table(style='width: 100%;')
        with moves_table:
            with thead():
                with tr():
                    th(cls.label('product.product', 'code'),
                        nowrap=True)
                    th(cls.label('product.template', 'name'),
                        nowrap=True)
                    if show_lots:
                        th(cls.label('stock.move', 'lot'))
                        if show_expiration:
                            th(cls.label('stock.lot',
                                'expiration_date'))
                        else:
                            th('', cls='hide')
                    else:
                        th('', cls='hide')
                    th(cls.label('stock.move', 'quantity'),
                        cls='text-right', nowrap=True)
                    th(cls.label('stock.move', 'unit'),
                        nowrap=True)
                    if valued:
                        th(cls.label('stock.move', 'base_price'),
                            cls='text-right')
                        th('', cls='text-right')
                        th(cls.label('stock.move', 'amount'),
                            cls='text-right')
                    else:
                        th('', cls='hide')
                        th('', cls='hide')
                        th('', cls='hide')
            with tbody(cls='border'):
                for move in document.moves:
                    with tr():
                        td(move.product and move.product.render.code or '-')
                        td(move.product and move.product.render.name or '-')
                        if show_lots:
                            td(move.lot and move.lot.raw.number or '')
                            if move.raw.lot and getattr(
                                    move.lot.raw, 'expiration_date', None):
                                td(move.lot.render.expiration_date)
                            else:
                                td('')
                        else:
                            td('')
                        td(move.render.quantity, cls='text-right')
                        td(move.unit.render.name)
                        if valued:
                            base_price = getattr(move.raw, 'base_price', None)
                            discount = getattr(move.raw, 'discount', None)
                            amount = getattr(move.raw, 'amount', None)
                            td(move.render.base_price
                                if base_price is not None else '',
                                cls='text-right', nowrap=True)
                            if discount:
                                td(move.render.discount, cls='text-right',
                                    nowrap=True)
                            else:
                                td('', cls='text-right', nowrap=True)
                            td(move.render.amount if amount is not None else '',
                                cls='text-right', nowrap=True)
                        else:
                            td('', cls='hide')
                            td('', cls='hide')
                            td('', cls='hide')
        return moves_table

    @classmethod
    def show_restocking_list_info(cls, record):
        title = cls.document_title(record.raw.__name__)
        container = div()
        with container:
            p(record.company.render.rec_name)
            h1(_('Restocking List'), cls='title')
            h1('%s: %s' % (title,
                record.render.number if record.raw.number else ''), cls='document')
            h2('%s: %s' % (
                cls.label('stock.shipment.in', 'reference'),
                record.render.origins if record.raw.origins
                else record.render.reference or ''), cls='document')
            h2('%s: %s' % (
                cls.label('stock.shipment.in', 'supplier'),
                record.supplier.render.rec_name or ''), cls='document')
            h2('%s: %s' % (
                cls.message('stock.msg_shipment_planned_date'),
                record.render.planned_date or ''), cls='document')
            h2('%s: %s' % (
                cls.label('stock.shipment.in', 'warehouse'),
                record.warehouse.render.rec_name), cls='document')
        return container

    @classmethod
    def show_restocking_list_moves(cls, shipment):
        if shipment.raw.state in ('cancelled', 'draft'):
            moves = shipment.incoming_moves
        else:
            moves = (shipment.incoming_moves if
                shipment.warehouse_input == shipment.warehouse_storage
                else shipment.inventory_moves)
        moves_table = table(style='width:100%;')
        with moves_table:
            with thead():
                with tr():
                    th(cls.label('stock.move', 'from_location'),
                        nowrap=True)
                    th(cls.label('stock.move', 'to_location'),
                        nowrap=True)
                    th(cls.label('stock.move', 'product'),
                        nowrap=True)
                    if shipment.raw.show_lots:
                        th(cls.label('stock.move', 'lot'),
                            nowrap=True)
                    th(cls.label('stock.move', 'quantity'),
                        nowrap=True)
            with tbody(cls='border'):
                for move in moves:
                    with tr():
                        td(move.from_location.render.rec_name)
                        td(move.to_location.render.rec_name)
                        td(move.product.render.rec_name)
                        if shipment.raw.show_lots:
                            lot_value = ''
                            if move.lot:
                                lot_value = move.lot.render.number
                                if (move.raw.lot
                                        and getattr(move.lot.raw,
                                            'expiration_date', None)):
                                    lot_value += ' (%s)' % (
                                        move.lot.render.expiration_date)
                            td(lot_value)
                        td(move.render.quantity)
        return moves_table

class StockInventoryReportMixin:
    blind = False

    @classmethod
    def css(cls, action, data, records):
        css = super().css(action, data, records) or ''
        now = datetime.now().strftime('%d/%m/%Y %H:%M')
        return '%s\n%s' % (
            css,
            ('@page {'
             '@bottom-left {'
             'content: "%s";'
             "font-family: 'Arial';"
             'font-size: 9px;'
             'padding-bottom: 0.5cm;'
             '}'
             '}') % now)

    @classmethod
    def get_report_company(cls):
        Company = Pool().get('company.company')
        company_id = Transaction().context.get('company')
        if not company_id:
            return None
        return DualRecord(Company(company_id))

    @classmethod
    def get_locations_label(cls):
        Location = Pool().get('stock.location')
        location_ids = Transaction().context.get('locations') or []
        if not location_ids:
            return ''
        locations = Location.browse(location_ids)
        labels = []
        for location in locations:
            if getattr(location, 'code', None):
                labels.append('%s [%s]' % (
                    location.name.strip(), location.code.strip()))
            else:
                labels.append(location.name.strip())
        return ' / '.join(labels)

    @classmethod
    def show_inventory_lines(cls, inventory):
        show_lots = inventory.raw.show_lots
        blind = cls.blind
        lines_table = table(style='width:100%;')
        with lines_table:
            with thead():
                th(cls.label('stock.inventory.line', 'product'),
                    nowrap=True)
                if show_lots:
                    th(cls.label('stock.inventory.line', 'lot'),
                        nowrap=True)
                if not blind:
                    th(cls.label('stock.inventory.line',
                        'expected_quantity'), cls='text-right')
                th(cls.label('stock.inventory.line', 'quantity'),
                    cls='text-right')
            with tbody(cls='border'):
                for line in inventory.lines:
                    with tr(style='border-bottom: 1px solid #cfcfcf;'):
                        td('%s - %s' % (
                            line.product and line.product.render.code,
                            line.product and line.product.render.name))
                        if show_lots:
                            td(line.raw.lot and line.lot.render.number or '')
                        if not blind:
                            td(line.render.expected_quantity or 0,
                                cls='text-right')
                        td('' if blind else (line.render.quantity or 0),
                            cls='text-right')
        return lines_table

    @classmethod
    def show_inventory_valued_lines(cls, records):
        company = cls.get_report_company()
        currency_symbol = (company.currency.render.symbol
            if company and company.raw.currency else '')
        total_cost_value = 0
        lines_table = table(style='width:100%;')
        with lines_table:
            with thead():
                th(cls.label('product.product', 'code'), nowrap=True)
                th(cls.label('product.template', 'name'), nowrap=True)
                th(cls.label('product.product', 'quantity'),
                    cls='text-right')
                th(cls.label('product.product', 'cost_value'),
                    cls='text-right')
            with tbody(cls='border'):
                for record in sorted(records, key=lambda r: (
                        r.render.code or '',
                        r.render.rec_name or '')):
                    total_cost_value += record.raw.cost_value or 0
                    with tr(style='border-bottom: 1px solid #cfcfcf;'):
                        td(record.render.code)
                        td(record.render.rec_name)
                        td(record.render.quantity, cls='text-right')
                        td('%s %s' % (
                                record.render.cost_value,
                                currency_symbol) if currency_symbol
                            else record.render.cost_value,
                            cls='text-right')
                with tr():
                    td('')
                    td('')
                    td(strong(_('Inventory Total')), cls='text-right')
                    td('%s %s' % (
                            render(total_cost_value),
                            currency_symbol) if currency_symbol
                        else render(total_cost_value),
                        cls='text-right')
        return lines_table

    @classmethod
    def inventory_valued_header(cls, action, data, records):
        company = cls.get_report_company()
        locations = cls.get_locations_label()
        header = div()
        with header:
            with header_tag(id='header'):
                with table():
                    with tr():
                        with td(cls='party_info', valign='top'):
                            cls.show_company_info(company)
                        with td(valign='top'):
                            h1(action.name, cls='document')
                            if locations:
                                h2(locations, cls='document')
        return header

    @classmethod
    def inventory_valued_body(cls, action, data, records):
        container = div()
        with container:
            container.add(cls.show_inventory_valued_lines(records))
        return container


class StockInventoryReport(StockInventoryReportMixin, StockReportMixin,
        metaclass=PoolMeta):
    __name__ = 'stock.inventory'
    _single = True

    @classmethod
    def header(cls, action, data, records):
        record, = records
        company = record.company
        header = div()
        with header:
            with header_tag(id='header'):
                with table():
                    with tr():
                        with td(cls='party_info', valign='top'):
                            cls.show_company_info(company)
                        with td(valign='top'):
                            strong('%s:' % cls.label(
                                'stock.inventory', 'number'))
                            raw(' %s' % record.render.number)
                            br()
                            strong('%s:' % cls.label(
                                'stock.inventory', 'date'))
                            raw(' %s' % record.render.date)
                            br()
                            strong('%s:' % cls.label(
                                'stock.inventory', 'location'))
                            raw(' %s' % record.location.render.name)
        return header

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_inventory_lines(record))
        return container


class StockBlindInventoryReport(StockInventoryReport):
    __name__ = 'stock.inventory.blind'
    blind = True


class InventoryValuedReport(StockInventoryReportMixin, StockReportMixin):
    __name__ = 'stock.inventory.valued'
    _single = False

    @classmethod
    def header(cls, action, data, records):
        return cls.inventory_valued_header(action, data, records)

    @classmethod
    def body(cls, action, data, records):
        return cls.inventory_valued_body(action, data, records)


class LocationInventoryValuedReport(StockInventoryReportMixin,
        StockReportMixin):
    __name__ = 'stock.location.inventory.valued'
    _single = False

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(locations=ids):
            return super().execute(ids, data)

    @classmethod
    def _get_records(cls, ids, model, data):
        pool = Pool()
        Product = pool.get('product.product')
        product_ids = []
        pbl = Product.products_by_location(ids, with_childs=True)
        for key, value in pbl.items():
            if value != 0 and key[1] not in product_ids:
                product_ids.append(key[1])
        with Transaction().set_context(locations=ids):
            return Product.browse(product_ids)

    @classmethod
    def header(cls, action, data, records):
        return cls.inventory_valued_header(action, data, records)

    @classmethod
    def body(cls, action, data, records):
        return cls.inventory_valued_body(action, data, records)


class DeliveryNoteReport(StockReportMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.delivery_note'
    _single = True

    @classmethod
    def show_document_info(cls, record):
        title = cls.document_title(record.raw.__name__)
        document_date = (record.render.effective_date
            if getattr(record.raw, 'effective_date', None) else '')
        container = div()
        with container:
            if record.raw.state not in ['assigned', 'picked', 'packed', 'done']:
                h1(_('Draft'), cls='document')
            h1('%s: %s' % (title,
                record.render.number if record.raw.number else ''),
                cls='document')
            h2('%s: %s' % (
                cls.message('stock.msg_shipment_effective_date'),
                document_date), cls='document')
            sale_references = getattr(record.raw, 'sale_references', None)
            if sale_references:
                h2('%s: %s' % (
                    cls.label(record.raw.__name__,
                        'sale_references'),
                    record.render.sale_references), cls='document')
        return container

    @classmethod
    def header(cls, action, data, records):
        record, = records
        return cls._header_with_document_info(
            action, data, records, cls.show_document_info(record))

    @classmethod
    def footer(cls, action, data, records):
        record, = records
        return cls._footer(action, data, records)

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_stock_moves(record, valued=False))
            if getattr(record.raw, 'carrier', None):
                container.add(cls.show_carrier(record.carrier))
            if getattr(record.raw, 'comment', None):
                h4(cls.label(record.raw.__name__, 'comment'))
                p(raw(record.render.comment))
        return container


class ValuedDeliveryNoteReport(DeliveryNoteReport, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.valued_delivery_note'
    _single = True

    @classmethod
    def last_footer(cls, action, data, records):
        record, = records
        last_footer = div()
        with last_footer:
            with div(id='last-footer', align='center'):
                with table(id='totals', cls='condensed'):
                    with tr():
                        td('')
                        with td():
                            cls.show_totals(record)
        return last_footer

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_stock_moves(record, valued=True))
            if getattr(record.raw, 'carrier', None):
                p(cls.show_carrier(record.carrier))
            if getattr(record.raw, 'comment', None):
                h4(cls.label(record.raw.__name__, 'comment'))
                p(raw(record.render.comment))
        return container


class PickingNoteReport(StockReportMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.picking_note'
    _single = True

    @classmethod
    def language(cls, records):
        return Transaction().language or 'en'

    @classmethod
    def show_document_info(cls, record):
        title = cls.document_title(record.raw.__name__)
        document_date = (record.render.effective_date
            if getattr(record.raw, 'effective_date', None) else '')
        label_package = None
        if getattr(record.raw, 'number_packages', None):
            label_package = cls.label(
                record.raw.__name__, 'number_packages')
        container = div()
        with container:
            if record.raw.state not in ['assigned', 'picked', 'packed', 'done']:
                h1(_('Draft'), cls='document')
            h1('%s: %s' % (title,
                record.render.number if record.raw.number else ''),
                cls='document')
            h2('%s: %s' % (
                cls.message('stock.msg_shipment_effective_date'),
                document_date), cls='document')
            if label_package:
                h3('%s: %s' % (
                    label_package, record.render.number_packages),
                    cls='document')
        return container

    @classmethod
    def header(cls, action, data, records):
        record, = records
        return cls._header_with_document_info(
            action, data, records, cls.show_document_info(record))

    @classmethod
    def footer(cls, action, data, records):
        record, = records
        return cls._footer(action, data, records)

    @classmethod
    def body(cls, action, data, records):
        record, = records
        moves = record.inventory_moves or record.outgoing_moves
        container = div()
        with container:
            container.add(cls.show_picking_moves(moves, record.raw.show_lots))
        return container


class InternalPickingNoteReport(StockReportMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal_picking_note'
    _single = True

    @classmethod
    def language(cls, records):
        return Transaction().language or 'en'

    @classmethod
    def show_document_info(cls, record):
        title = cls.document_title(record.raw.__name__)
        document_date = (record.render.effective_date
            if getattr(record.raw, 'effective_date', None) else '')
        label_package = None
        if getattr(record.raw, 'number_packages', None):
            label_package = cls.label(
                record.raw.__name__, 'number_packages')
        container = div()
        with container:
            if record.raw.state not in ['assigned', 'picked', 'packed', 'done']:
                h1(_('Draft'), cls='document')
            h1('%s: %s' % (title,
                record.render.number if record.raw.number else ''),
                cls='document')
            h2('%s: %s' % (
                cls.message('stock.msg_shipment_effective_date'),
                document_date), cls='document')
            if label_package:
                h3('%s: %s' % (
                    label_package, record.render.number_packages),
                    cls='document')
            h3('%s: %s' % (
                cls.label('stock.shipment.internal',
                    'from_location'),
                record.from_location.render.name), cls='document')
            h3('%s: %s' % (
                cls.label('stock.shipment.internal',
                    'to_location'),
                record.to_location.render.name), cls='document')
        return container

    @classmethod
    def header(cls, action, data, records):
        record, = records
        return cls._header_with_document_info(
            action, data, records, cls.show_document_info(record))

    @classmethod
    def footer(cls, action, data, records):
        record, = records
        return cls._footer(action, data, records)

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_internal_picking_moves(
                record, record.raw.show_lots))
        return container


class CustomerRefundNoteReport(StockReportMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.refund_note'
    _single = True

    @classmethod
    def show_document_info(cls, record):
        title = cls.document_title(record.raw.__name__)
        document_date = (record.render.effective_date
            if getattr(record.raw, 'effective_date', None) else '')
        container = div()
        with container:
            h1('%s: %s' % (title,
                record.render.number if record.raw.number else ''),
                cls='document')
            h2('%s: %s' % (
                cls.message('stock.msg_shipment_effective_date'),
                document_date), cls='document')
        return container

    @classmethod
    def header(cls, action, data, records):
        record, = records
        return cls._header_with_document_info(
            action, data, records, cls.show_document_info(record))

    @classmethod
    def footer(cls, action, data, records):
        record, = records
        return cls._footer(action, data, records)

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_customer_return_stock_moves(
                record, valued=False))
            if getattr(record.raw, 'carrier', None):
                container.add(cls.show_carrier(record.carrier))
            if getattr(record.raw, 'comment', None):
                br()
                br()
                strong(cls.label(record.raw.__name__, 'comment'))
                br()
                raw(record.render.comment)
        return container


class RefundNoteReport(CustomerRefundNoteReport, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.refund_note'
    _single = True

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_return_stock_moves(record, valued=False))
            if getattr(record.raw, 'carrier', None):
                container.add(cls.show_carrier(record.carrier))
            if getattr(record.raw, 'comment', None):
                br()
                br()
                strong(cls.label(record.raw.__name__, 'comment'))
                br()
                raw(record.render.comment)
        return container


class SupplierRestockingListReport(StockReportMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in.restocking_list'
    _single = True

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_restocking_list_info(record))
            container.add(cls.show_restocking_list_moves(record))
        return container


class StockTotalInventoryStart(ModelView):
    'Stock Total Inventory'
    __name__ = 'html_report.stock.print_total_inventory.start'

    date = fields.Date("Date")
    products = fields.Many2Many(
        'product.product', None, None, "Products",
        domain=[
            ('type', '=', 'goods'),
            ('consumable', '!=', True),
            ])
    locations = fields.Many2Many(
        'stock.location', None, None, "Locations",
        domain=[('type', '=', 'warehouse')], required=True)
    output_format = fields.Selection([
        ('pdf', "PDF"),
        ('xlsx', "Excel"),
        ('html', "HTML")],
        "Format", required=True)
    order = fields.Selection([
        ('location', 'Location'),
        ('product', 'Product'),
        ], "Order", required=True)
    quantities = fields.Selection([
        ('all', 'All'),
        ('positive', 'Positive'),
        ('negative', 'Negative'),
        ], "Quantities", required=True)
    timeout = fields.Integer('Timeout', required=True,
        help='Timeout in seconds')

    @staticmethod
    def default_locations():
        warehouse = Transaction().context.get('warehouse')
        if warehouse:
            return [warehouse]
        return []

    @staticmethod
    def default_quantities():
        return 'positive'

    @staticmethod
    def default_timeout():
        return 120


class StockTotalInventoryLotStart(metaclass=PoolMeta):
    __name__ = 'html_report.stock.print_total_inventory.start'

    group_by_lot = fields.Boolean('Group by Lot')


class StockTotalInventory(Wizard):
    'Stock Total Inventory'
    __name__ = 'html_report.stock.print_total_inventory'

    start = StateView('html_report.stock.print_total_inventory.start',
        'html_report.print_total_inventory_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
            ])
    print_ = StateReport('html_report.stock.total_inventory')

    def default_start(self, fields):
        return {
            'output_format': 'pdf',
            'order': 'location',
            }

    def do_print_(self, action):
        data = {
            'date': self.start.date,
            'quantities': self.start.quantities,
            'group_by_lot': getattr(self.start, 'group_by_lot', False),
            'products': [x.id for x in self.start.products],
            'locations': [x.id for x in self.start.locations],
            'output_format': self.start.output_format,
            'order': self.start.order,
            'timeout': self.start.timeout,
            }
        if self.start.output_format == 'xlsx':
            ActionReport = Pool().get('ir.action.report')
            action_report, = ActionReport.search([
                    ('report_name', '=', 'html_report.stock.total_inventory_xlsx'),
                    ])
            action = action_report.action.get_action_value()
        return action, data

    def transition_print_(self):
        return 'end'


class StockTotalInventoryReport(StockInventoryReportMixin, StockReportMixin):
    'Total Inventory Report'
    __name__ = 'html_report.stock.total_inventory'
    _single = False

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__['execute'] = RPC(False)

    @classmethod
    def css_body(cls, action, data, records):
        css = super().css_body(action, data, records)
        if data.get('output_format') != 'pdf':
            css += (
                '\nheader { position: static; padding-top: 0; '
                'padding-left: 0; }\n'
            )
        return css

    @staticmethod
    def get_location_domain(data):
        return [
            ('parent', 'child_of', data['locations']),
            ('type', '=', 'storage'),
            ]

    @classmethod
    def get_stock_context(cls, data):
        return {}

    @classmethod
    def get_stock_grouping(cls, data):
        grouping = ('product',)
        if data.get('group_by_lot'):
            grouping += ('lot',)
        return grouping

    @classmethod
    def get_stock_grouping_key(cls, key, data):
        return key

    @classmethod
    def prepare(cls, data):
        pool = Pool()
        Company = pool.get('company.company')
        Location = pool.get('stock.location')
        Date = pool.get('ir.date')
        Product = pool.get('product.product')

        checker = TimeoutChecker(data.get('timeout', 60), TimeoutException)

        if data.get('group_by_lot'):
            Lot = pool.get('stock.lot')
        else:
            Lot = None

        with Transaction().set_context(_record_cache_size=100000):
            locations = Location.search(cls.get_location_domain(data),
                                        order=[('name', 'ASC')])
        location_ids = [l.id for l in locations]
        locations_by_id = {l.id: l for l in locations}
        checker.check()

        domain = [
            ('type', '=', 'goods'),
            ('consumable', '!=', True),
            ]
        if data['products']:
            domain.append(('id', 'in', data['products']))

        with Transaction().set_context(active_test=False,
                _record_cache_size=100000):
            products = Product.search(domain)
        products_by_id = {p.id: p for p in products}

        stock_date_end = data['date'] or Date.today()
        quantities = data.get('quantities', 'positive')

        quantities_by_key = {}
        with Transaction().set_context(
                stock_date_end=stock_date_end, **cls.get_stock_context(data)):
            grouping = cls.get_stock_grouping(data)
            for sub_products in grouped_slice(products, count=10000):
                checker.check()
                product_ids = [x.id for x in sub_products]
                pbl = Product.products_by_location(
                    location_ids,
                    grouping=grouping,
                    grouping_filter=(product_ids,))

                for key, qty in pbl.items():
                    key = cls.get_stock_grouping_key(key, data)
                    quantities_by_key[key] = quantities_by_key.get(key, 0) + qty

        records = []
        for key, qty in quantities_by_key.items():
            if not qty:
                continue
            if quantities == 'positive' and qty < 0:
                continue
            if quantities == 'negative' and qty > 0:
                continue
            record = {
                'quantity': qty,
                'location': locations_by_id[key[0]],
                'product': products_by_id[key[1]],
                }
            if data.get('group_by_lot'):
                record['lot'] = Lot(key[2]) if key[2] else None
            records.append(record)

        company_id = Transaction().context.get('company')
        parameters = {}
        parameters['company'] = (Company(company_id)
            if company_id is not None and company_id >= 0 else None)
        parameters['now'] = format_datetime(
            datetime.now(), format='short',
            locale=Transaction().language or 'en')
        parameters['sort_attribute'] = ('product.rec_name'
            if data['order'] == 'product' else 'location.rec_name')
        parameters['has_lot'] = data.get('group_by_lot')
        parameters['timeout'] = data.get('timeout') - checker.elapsed
        return records, parameters

    @classmethod
    def _sort_value(cls, item, sort_attribute):
        value = item
        for part in sort_attribute.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, '')
        return value or ''

    @classmethod
    def show_lines(cls, records, parameters):
        has_lot = parameters.get('has_lot')
        sort_attribute = parameters.get('sort_attribute')
        lines_table = table()
        with lines_table:
            with thead():
                with tr():
                    th(_('Location'))
                    th(_('Product'))
                    if has_lot:
                        th(_('Lot'))
                    th(_('Quantity'), style='text-align: right')
            with tbody():
                for record in sorted(
                        records,
                        key=lambda item: cls._sort_value(
                            item, sort_attribute)):
                    product = record['product']
                    with tr():
                        td(record['location'].name)
                        td(product.rec_name)
                        if has_lot:
                            lot = record.get('lot')
                            td(lot.rec_name if lot else '')
                        td(render(
                                record['quantity'],
                                digits=product.default_uom.digits),
                            style='text-align: right')
        return lines_table

    @classmethod
    def report_title(cls, parameters):
        company = parameters.get('company')
        company_name = company.rec_name if company else ''
        now = parameters.get('now', '')
        title = _('Total Inventory')
        return '%s - %s - %s' % (title, company_name or '', now)

    @classmethod
    def header(cls, action, data, records):
        parameters = data['parameters']
        company = cls.get_report_company()
        title = cls.report_title(parameters)
        header = div()
        with header:
            with header_tag(id='header'):
                with table():
                    with tr():
                        with td(cls='party_info', valign='top'):
                            cls.show_company_info(company)
                        with td(valign='top'):
                            h1(title, cls='document')
        return header

    @classmethod
    def body(cls, action, data, records):
        parameters = data['parameters']
        container = div()
        with container:
            if data.get('output_format') != 'pdf':
                container.add(cls.header(action, data, records))
            if data['records']:
                container.add(cls.show_lines(data['records'], parameters))
            else:
                strong(_('No records found'))
        return container

    @classmethod
    def execute(cls, ids, data):
        action, model = cls.get_action(data)
        cls.check_access(action, model, ids)
        side_margin = action.html_side_margin
        if side_margin is None:
            side_margin = cls.side_margin
        extra_vertical_margin = action.html_extra_vertical_margin
        if extra_vertical_margin is None:
            extra_vertical_margin = cls.extra_vertical_margin
        with Transaction().set_context(active_test=False):
            records, parameters = cls.prepare(data)
        report_data = dict(data)
        report_data['records'] = records
        report_data['parameters'] = parameters
        output_format = data.get('output_format', action.extension or 'pdf')
        with Transaction().set_context(
                html_report=action.id,
                address_with_party=False,
                output_format=output_format):
            oext, content = cls._execute_dominate_report(
                [], report_data, action,
                side_margin=side_margin,
                extra_vertical_margin=extra_vertical_margin)
        if content is None:
            content = ''
        if not isinstance(content, str):
            content = bytes(content)
        return oext, content, cls.get_direct_print(action), action.name


class StockTotalInventoryXlsxReport(Report):
    __name__ = 'html_report.stock.total_inventory_xlsx'

    @classmethod
    def execute(cls, ids, data):
        pool = Pool()
        ActionReport = pool.get('ir.action.report')
        action_report, = ActionReport.search([
                ('report_name', '=', cls.__name__)
                ])
        cls.check_access(action_report, action_report.model, ids)
        report = pool.get('html_report.stock.total_inventory', type='report')
        with Transaction().set_context(active_test=False):
            records, parameters = report.prepare(data)
        content = cls.get_content(records, parameters)
        return 'xlsx', content, action_report.direct_print, action_report.name

    @classmethod
    def get_content(cls, records, parameters):
        wb = Workbook()
        ws = wb.active
        ws.title = _('Total Inventory')[:31]

        title = StockTotalInventoryReport.report_title(parameters)
        ws.append([title])
        company = parameters.get('company')
        if company:
            ws.append([company.rec_name])
        if parameters.get('now'):
            ws.append([parameters['now']])
        ws.append([])

        has_lot = parameters.get('has_lot')
        sort_attribute = parameters.get('sort_attribute')
        headers = [_('Location'), _('Product')]
        if has_lot:
            headers.append(_('Lot'))
        headers.append(_('Quantity'))
        ws.append(headers)

        for record in sorted(
                records,
                key=lambda item: StockTotalInventoryReport._sort_value(
                    item, sort_attribute)):
            product = record['product']
            row = [record['location'].name, product.rec_name]
            if has_lot:
                lot = record.get('lot')
                row.append(lot.rec_name if lot else '')
            row.append(record['quantity'])
            ws.append(row)

        with NamedTemporaryFile() as tmp_file:
            wb.save(tmp_file.name)
            tmp_file.seek(0)
            return bytes(tmp_file.read())
