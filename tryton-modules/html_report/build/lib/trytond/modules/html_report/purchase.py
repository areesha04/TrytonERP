from trytond.pool import PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.modules.html_report.template import HTMLPartyInfoMixin
from trytond.modules.html_report.discount import HTMLDiscountReportMixin
from trytond.modules.html_report.dominate_report import DominateReport
from dominate.util import raw
from dominate.tags import (div, footer as footer_tag, h1, h2, h4,
    header as header_tag, img, p, strong, table, tbody, td, th, thead, tr)


class Purchase(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'purchase.purchase'

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls.html_party.context = {'company': Eval('company', -1)}
        cls.html_party.depends = ['company']

    def get_html_address(self, name):
        return (self.invoice_address and self.invoice_address.id
            or super().get_html_address(name))


class PurchaseLineDiscount(HTMLDiscountReportMixin, metaclass=PoolMeta):
    __name__ = 'purchase.line'


class PurchaseReportMixin(DominateReport):
    _single = True

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
    def show_payment_info(cls, document):
        return cls.common().show_payment_info(document)

    @classmethod
    def show_totals(cls, record):
        return cls.common().show_totals(record)

    @classmethod
    def show_purchase_lines(cls, document, simplified=False):
        lines_table = table(style='width:100%;')
        with lines_table:
            with thead():
                with tr():
                    th(cls.label('product.product', 'code'),
                        nowrap=True)
                    th(cls.label('product.template', 'name'),
                        nowrap=True)
                    th(cls.label('purchase.line', 'quantity'),
                        cls='text-right', nowrap=True)
                    if not simplified:
                        th(cls.label('purchase.line', 'unit_price'),
                            cls='text-right', nowrap=True)
                        th('')
                        th(cls.label('purchase.line', 'amount'),
                            cls='text-right', nowrap=True)
            with tbody(cls='border'):
                for line in document.lines:
                    if line.raw.type == 'line':
                        with tr():
                            if line.raw.description:
                                td(raw(line.render.description), colspan='2')
                            elif line.raw.product_supplier and line.product_supplier.raw.name:
                                td(line.product_supplier.render.code or '-')
                                td(line.product_supplier.render.name or '-')
                            elif line.raw.product:
                                td(line.product and line.product.render.code or '-')
                                td(line.product and line.product.render.name or '-')

                            qty = '%s' % line.render.quantity
                            if line.unit and line.unit.render.symbol:
                                qty += ' %s' % line.unit.render.symbol
                            td(qty, cls='text-right')

                            if not simplified:
                                base_price = getattr(line.raw, 'base_price', None)
                                discount = getattr(line.raw, 'discount', None)
                                if base_price:
                                    td('%s %s' % (
                                        line.render.base_price,
                                        line.purchase.currency.render.symbol),
                                        cls='text-right')
                                    if discount:
                                        td(line.render.discount, cls='text-right')
                                    else:
                                        td(' ')
                                else:
                                    td('%s %s' % (
                                        line.render.unit_price,
                                        line.purchase.currency.render.symbol),
                                        cls='text-right')
                                    td('')
                                td('%s %s' % (
                                    line.render.amount,
                                    line.purchase.currency.render.symbol),
                                    cls='text-right')
                    elif line.raw.type == 'comment':
                        with tr():
                            td(line.render.type)
                            td(raw(line.render.description),
                                colspan='2' if simplified else '5')
                    elif line.raw.type == 'title':
                        with tr():
                            with td(colspan='3' if simplified else '6'):
                                strong(line.render.description)
                    elif line.raw.type == 'subtotal' and not simplified:
                        with tr():
                            with td(colspan='5'):
                                strong(line.render.description)
                            with td(cls='text-right'):
                                strong('%s %s' % (
                                    line.render.amount,
                                    line.purchase.currency.render.symbol))
        return lines_table

    @classmethod
    def show_document_info(cls, record):
        if record.raw.state in ('quotation', 'draft'):
            title = record.render.state
        else:
            title = cls.label(record.raw.__name__)

        document_date = record.raw.purchase_date and record.render.purchase_date or ''
        label_date = cls.label(record.raw.__name__, 'purchase_date')

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
        return container

    @classmethod
    def header(cls, action, data, records):
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
                        with td():
                            cls.show_document_info(record)
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
            container.add(cls.show_purchase_lines(record))
            if record.raw.comment:
                h4(cls.label('purchase.purchase', 'comment'))
                p(raw(record.render.comment))

        return container


class PurchaseReport(PurchaseReportMixin):
    __name__ = 'purchase.purchase'


class PurchaseSimplifiedReport(PurchaseReportMixin):
    __name__ = 'purchase.purchase.simplified'

    @classmethod
    def show_purchase_lines(cls, document, simplified=False):
        # Force simplified to True as the report is for simplified version of
        # the document
        return super().show_purchase_lines(document, simplified=True)

    @classmethod
    def show_totals(cls, record):
        # Hide totals in simplified report
        return

    @classmethod
    def last_footer(cls, action, data, records):
        # Hide totals in simplified report
        return
