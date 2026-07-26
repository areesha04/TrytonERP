from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.modules.html_report.template import HTMLPartyInfoMixin
from trytond.modules.html_report.dominate_report import DominateReport
from trytond.modules.html_report.discount import HTMLDiscountReportMixin
from trytond.modules.html_report.tools import label
from trytond.transaction import Transaction
from trytond.modules.xgettext import _
from dominate.util import raw
from dominate.tags import (div, footer as footer_tag, h1, h2, h3, h4,
    header as header_tag, img, p, strong, table, tbody, td, th, thead, tr)


class Sale(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls.html_party.context = {'company': Eval('company', -1)}
        cls.html_party.depends = ['company']

    def get_html_address(self, name):
        return (self.invoice_address and self.invoice_address.id
            or super().get_html_address(name))

    def get_html_second_address(self, name):
        return (self.shipment_address and self.shipment_address.id
            or super().get_html_second_address(name))

    def get_html_second_address_label(self, name):
        return label(self.__name__, 'shipment_address')


class SaleLineDiscount(HTMLDiscountReportMixin, metaclass=PoolMeta):
    __name__ = 'sale.line'


class SaleReport(DominateReport):
    __name__ = 'sale.sale'
    _single = True

    @classmethod
    def _is_proforma(cls, action):
        return bool(action and action.name == 'Proforma')

    @classmethod
    def title(cls, action, data, records):
        if cls._is_proforma(action):
            record = records[0] if records else None
            return 'Proforma %s' % (record and record.render.number or '')
        return super().title(action, data, records)

    @classmethod
    def language(cls, records):
        record = records[0] if records else None
        if record and record.party and record.party.raw.lang:
            return record.party.raw.lang.code
        return Transaction().language or 'en'

    @classmethod
    def show_company_info(cls, company, show_party=True,
            show_contact_mechanism=True, show_phone=True,
            show_email=True, show_website=True):
        return cls.common().show_company_info(
            company, show_party=show_party,
            show_contact_mechanism=show_contact_mechanism,
            show_phone=show_phone,
            show_email=show_email,
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
    def show_payment_info(cls, document):
        return cls.common().show_payment_info(document)

    @classmethod
    def show_totals(cls, record):
        return cls.common().show_totals(record)

    @classmethod
    def show_sale_lines(cls, document):
        lines_table = table(style='width:100%;')
        with lines_table:
            with thead():
                with tr():
                    th(cls.label('product.product', 'code'),
                        nowrap=True)
                    th(cls.label('product.template', 'name'),
                        nowrap=True)
                    th(cls.label('sale.line', 'quantity'),
                        cls='text-right', nowrap=True)
                    th(cls.label('sale.line', 'unit_price'),
                        cls='text-right', nowrap=True)
                    th('')
                    th(cls.label('sale.line', 'amount'),
                        cls='text-right', nowrap=True)
            with tbody(cls='border'):
                for line in document.lines:
                    if line.raw.type == 'line':
                        with tr():
                            if line.raw.description:
                                td(raw(line.render.description), colspan='2')
                            else:
                                td(line.product and line.product.render.code or '-')
                                td(line.product and line.product.render.name or '-')
                            qty = '%s' % line.render.quantity
                            if line.unit:
                                qty += ' %s' % line.unit.render.symbol
                            td(qty, cls='text-right')
                            base_price = getattr(line.raw, 'base_price', None)
                            discount = getattr(line.raw, 'discount', None)
                            if base_price:
                                td('%s %s' % (
                                    line.render.base_price,
                                    line.sale.currency.render.symbol),
                                    cls='text-right')
                                if discount:
                                    td(line.render.discount, cls='text-right')
                                else:
                                    td(' ')
                            else:
                                td('%s %s' % (
                                    line.render.unit_price,
                                    line.sale.currency.render.symbol),
                                    cls='text-right')
                                td('')
                            td('%s %s' % (
                                line.render.amount,
                                line.sale.currency.render.symbol),
                                cls='text-right')
                    elif line.raw.type == 'comment':
                        with tr():
                            td(line.render.type)
                            td(raw(line.render.description), colspan='5')
                    elif line.raw.type == 'title':
                        with tr():
                            with td(colspan='6'):
                                strong(line.render.description)
                    elif line.raw.type == 'subtotal':
                        with tr():
                            with td(colspan='5'):
                                strong(line.render.description)
                            with td(cls='text-right'):
                                strong('%s %s' % (
                                    line.render.amount,
                                    line.sale.currency.render.symbol))
        return lines_table

    @classmethod
    def show_document_info(cls, record, is_proforma=False):
        if is_proforma:
            title = _('Proforma')
        else:
            if record.raw.state in ('quotation', 'draft'):
                title = record.render.state
            else:
                title = cls.label(record.raw.__name__)

        document_date = record.raw.sale_date and record.render.sale_date or ''
        label_date = cls.label(record.raw.__name__, 'sale_date')

        container = div()
        with container:
            h1('%s: %s' % (title, record.render.number
                if record.raw.number else ''), cls='document')
            if document_date:
                h2('%s: %s' % (label_date, document_date), cls='document')
            if record.raw.reference:
                h2('%s: %s' % (
                    cls.label(record.raw.__name__, 'reference'),
                    record.render.reference), cls='document')
            if getattr(record.raw, 'carrier', None) and not is_proforma:
                h3('%s: %s' % (
                    cls.label(record.raw.__name__, 'carrier'),
                    record.carrier.party.render.name), cls='document')
        return container

    @classmethod
    def header(cls, action, data, records):
        record, = records
        company = record.company
        is_proforma = cls._is_proforma(action)

        header = div()
        with header:
            with header_tag(id='header'):
                with table():
                    with tr():
                        with td():
                            if company.render.logo:
                                img(cls='logo', src=company.render.logo)
                        with td():
                            cls.show_document_info(record, is_proforma=is_proforma)
                    with tr():
                        with td(cls='party_info'):
                            cls.show_company_info(company)
                        with td(cls='party_info'):
                            party = record.html_party
                            tax_identifier = record.html_tax_identifier
                            address = record.html_address
                            second_address_label = record.render.html_second_address_label
                            second_address = record.html_second_address
                            cls.show_party_info(party, tax_identifier, address,
                                second_address_label, second_address)
        return header

    @classmethod
    def footer(cls, action, data, records):
        record, = records
        company = record.company
        footer = div()
        with footer:
            with footer_tag(id='footer', align='center'):
                cls.show_footer(company)
        return footer

    @classmethod
    def last_footer(cls, action, data, records):
        record, = records
        last_footer = div()
        with last_footer:
            with div(id='last-footer', align='center'):
                with table(id='totals', cls='condensed'):
                    with tr():
                        with td():
                            cls.show_payment_info(record)
                        with td():
                            cls.show_totals(record)
        return last_footer

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_sale_lines(record))
            if record.raw.comment:
                h4(cls.label('sale.sale', 'comment'))
                p(raw(record.render.comment))

        return container
