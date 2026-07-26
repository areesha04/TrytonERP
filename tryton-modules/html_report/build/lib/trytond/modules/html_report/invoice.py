from collections import defaultdict
from decimal import Decimal
from itertools import groupby
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.html_report.template import HTMLPartyInfoMixin
from trytond.modules.html_report.engine import DualRecord, render as html_render
from trytond.modules.html_report.dominate_report import DominateReport
from trytond.modules.html_report.discount import HTMLDiscountReportMixin
from trytond.modules.xgettext import _
from dominate.util import raw
from dominate.tags import (div, footer as footer_tag, h1, h2, h4,
    header as header_tag, img, p, strong, style, table, tbody, td, th, thead,
    tr)


class Invoice(HTMLPartyInfoMixin, metaclass=PoolMeta):
    __name__ = 'account.invoice'
    html_lines_to_pay = fields.Function(fields.Many2Many(
            'account.move.line', None, None, 'HTML Lines to Pay'),
        'get_html_lines_to_pay')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.html_party.context = {'company': Eval('company', -1)}
        cls.html_party.depends = ['company']

    def get_html_address(self, name):
        return (self.invoice_address and self.invoice_address.id
            or super().get_html_address(name))

    @classmethod
    def get_html_lines_to_pay(cls, invoices, name):
        lines = defaultdict(list)
        for invoice in invoices:
            lines[invoice.id] = [l.id for l in sorted([line for line in invoice.lines_to_pay
                if not line.reconciliation and line.maturity_date],
                key=lambda x: x.maturity_date)]
        return lines

    @property
    def html_taxes(self):
        currency_digits = self.currency.digits
        precision = '0.' + '0' * currency_digits if currency_digits > 0 else '0'

        def default_amount():
            return {'base': Decimal(precision), 'amount': Decimal(precision)}

        taxes = defaultdict(default_amount)
        for tax in self.taxes:
            key = tax.tax or tax
            taxes[key]['base'] += tax.base
            taxes[key]['amount'] += tax.amount
            taxes[key]['legal_notice'] = tax.legal_notice
        return {DualRecord(k): v for k, v in taxes.items()}


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'
    shipment_key = fields.Function(fields.Char("Shipment Key",
        ), 'get_shipment_key')
    origin_line_key = fields.Function(fields.Char("Origin Line Key",
        ), 'get_origin_line_key')
    html_product_code = fields.Function(fields.Char(
        "HTML Code"), 'get_html_product_code')

    @classmethod
    def _get_shipment_origin(cls):
        return ['stock.shipment.out', 'stock.shipment.out.return',
            'stock.shipment.in', 'stock.shipment.in.return',
            'stock.shipment.drop']

    def get_shipment_key(self, name):
        if not hasattr(self, 'stock_moves'):
            return ''
        if not self.stock_moves:
            return ''
        shipment = self.stock_moves[0].shipment
        if not shipment:
            return ''
        return str(shipment)

    @classmethod
    def _get_origin_line_keys(cls):
        return {
            'sale.line': 'sale',
            'purchase.line': 'purchase',
            }

    def get_origin_line_key(self, name):
        models = self._get_origin_line_keys()
        if self.origin:
            model = getattr(self.origin, '__name__', None)
            if models.get(model):
                field = models.get(model)
                return str(getattr(self.origin, field))
        return ''

    def get_html_product_code(self, name):
        return self.product and self.product.code or ''


class InvoiceLineDiscount(HTMLDiscountReportMixin, metaclass=PoolMeta):
    __name__ = 'account.invoice.line'


class InvoiceReportMixin(DominateReport):
    _single = True
    show_header_level1 = True
    show_header_level2 = True

    @classmethod
    def language(cls, records):
        record = records[0] if records else None
        if record and record.party and record.party.raw.lang:
            return record.party.raw.lang.code
        return Transaction().language or 'en'

    @classmethod
    def _execute_dominate_report(cls, records, data, action, side_margin,
            extra_vertical_margin):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        Configuration = Pool().get('account.configuration')

        config = Configuration(1)
        extension, document = None, None
        is_html = Transaction().context.get('output_format') == 'html'

        to_invoice_cache = {}
        if config.use_invoice_report_cache:
            to_cache = [r for r in records
                            if r.raw.state in {'posted', 'paid'}
                            and r.raw.type == 'out'
                            and not r.raw.invoice_report_cache]

            for record in to_cache:
                extension, document = super()._execute_dominate_report([record], data, action,
                        side_margin, extra_vertical_margin)

                if isinstance(document, str):
                    document = bytes(document, 'utf-8')

                to_invoice_cache[record.raw.id] = {
                    'invoice_report_format': extension,
                    'invoice_report_cache': Invoice.invoice_report_cache.cast(document),
                    }

        # Check if the transaction is readonly or is_html
        if to_invoice_cache and not is_html and not Transaction().readonly:
            to_write = []
            for id, values in to_invoice_cache.items():
                # Re-instantiate because records are DualRecord
                to_write.extend(([Invoice(id)], {
                    'invoice_report_format': values['invoice_report_format'],
                    'invoice_report_cache': values['invoice_report_cache'],
                    }))
            Invoice.write(*to_write)

        documents = []
        for record in records:
            if to_invoice_cache.get(record.raw.id):
                extension = to_invoice_cache[record.raw.id]['invoice_report_format']
                document = to_invoice_cache[record.raw.id]['invoice_report_cache']
                documents.append(document)
            elif record.raw.invoice_report_cache:
                extension = record.raw.invoice_report_format
                document = record.raw.invoice_report_cache
                documents.append(document)
            else:
                extension, document = super()._execute_dominate_report([record], data, action,
                    side_margin, extra_vertical_margin)
                documents.append(document)
        if len(documents) > 1 and not is_html:
            extension = 'pdf'
            document = cls.merge_pdfs(documents)

        return extension, document

    @classmethod
    def _group_sorted(cls, items, keyfunc):
        sorted_items = sorted(items, key=lambda item: (keyfunc(item) is None,
            keyfunc(item)))
        groups = []
        for key, group in groupby(sorted_items, key=keyfunc):
            groups.append((key, list(group)))
        return groups

    @staticmethod
    def _normalize_group_key(value):
        return value or None

    @classmethod
    def hook_invoice_origin_lines(cls, shipment_record, origin_record,
            origin_lines):
        return origin_lines

    @classmethod
    def show_invoice_lines(cls, document):
        lines_table = table(style='width:100%;')
        with lines_table:
            with thead():
                with tr():
                    th(cls.label('product.product', 'code'),
                        nowrap=True)
                    th(cls.label('product.template', 'name'),
                        nowrap=True)
                    th(cls.label('account.invoice.line',
                        'quantity'), cls='text-right', nowrap=True)
                    th(cls.label('account.invoice.line',
                        'unit_price'), cls='text-right', nowrap=True)
                    th('')
                    th(cls.label('account.invoice.line',
                        'amount'), cls='text-right', nowrap=True)
            with tbody(cls='border'):
                lines = list(document.raw.lines or [])
                for key, grouped in cls._group_sorted(lines,
                        lambda line: cls._normalize_group_key(
                            line.shipment_key)):
                    if key:
                        key_record = cls.dualrecord(key)
                    else:
                        key_record = None
                    origin_groups = []
                    for key2, origin_lines in cls._group_sorted(grouped,
                            lambda line: cls._normalize_group_key(
                                line.origin_line_key)):
                        if key2:
                            key2_record = cls.dualrecord(key2)
                        else:
                            key2_record = None
                        hook_lines = cls.hook_invoice_origin_lines(
                            key_record, key2_record, origin_lines)
                        if hook_lines:
                            origin_groups.append((key2_record, hook_lines))
                    if not origin_groups:
                        continue
                    if cls.show_header_level1:
                        with tr():
                            header_cell = th(cls='sub_header_level1', colspan='6')
                            if key_record:
                                header_cell.add(raw('%s: %s' % (
                                    cls.label(key_record.raw.__name__),
                                    key_record.render.number)))
                                if key_record.raw.reference:
                                    header_cell.add(raw(' / %s' % key_record.render.reference))
                                if key_record.raw.effective_date:
                                    header_cell.add(raw(' %s: %s' % (
                                        cls.message(
                                            'stock.msg_shipment_effective_date'),
                                        key_record.render.effective_date)))
                    for key2_record, origin_lines in origin_groups:
                        if cls.show_header_level2:
                            with tr():
                                header_cell = th(cls=('sub_header_level2'
                                    if key2_record else 'sub_header_level1'),
                                    colspan='6')
                                if key2_record:
                                    header_cell.add(raw('%s: %s' % (
                                        cls.label(key2_record.raw.__name__),
                                        key2_record.render.number)))
                                    if key2_record.render.reference:
                                        header_cell.add(raw(' / %s' % key2_record.render.reference))
                                    if hasattr(key2_record.render, 'sale_date'):
                                        sale_date = key2_record.render.sale_date
                                        if sale_date:
                                            header_cell.add(raw(' %s: %s' % (
                                                cls.label(
                                                    key2_record.raw.__name__,
                                                    'sale_date'),
                                                sale_date)))
                        for line in origin_lines:
                            line = DualRecord(line)
                            if line.raw.type == 'line':
                                with tr():
                                    if line.raw.description:
                                        td('')
                                        td(raw(line.render.description))
                                    else:
                                        td(line.product and line.product.render.code or '')
                                        td(line.product and line.product.render.name or '')
                                    qty = '%s' % line.render.quantity
                                    if line.unit:
                                        qty += ' %s' % line.unit.render.symbol
                                    td(qty, cls='text-right')
                                    base_price = getattr(line.raw, 'base_price', None)
                                    discount = getattr(line.raw, 'discount', None)
                                    if base_price:
                                        td('%s %s' % (
                                            line.render.base_price,
                                            line.invoice.currency.render.symbol),
                                            cls='text-right')
                                        if discount:
                                            td(line.render.discount, cls='text-right')
                                        else:
                                            td(' ')
                                    else:
                                        td('%s %s' % (
                                            line.render.unit_price,
                                            line.invoice.currency.render.symbol),
                                            cls='text-right')
                                        td('')
                                    td('%s %s' % (
                                        line.render.amount,
                                        line.invoice.currency.render.symbol),
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
                                            line.invoice.currency.render.symbol))
                with tr(cls='b-hide'):
                    td(colspan='6')
        return lines_table

    @classmethod
    def show_invoice_lines_simplified(cls, document):
        lines_table = table(cls='table borderless', width='100%')
        with lines_table:
            with thead():
                th(cls.label('product.product', 'code'),
                    nowrap=True)
                th(cls.label('account.invoice.line',
                    'description'), nowrap=True)
                th(cls.label('account.invoice.line',
                    'quantity'), cls='text-right', nowrap=True)
                th(cls.label('account.invoice.line',
                    'unit_price'), cls='text-right', nowrap=True)
                th(cls.label('account.invoice.line',
                    'amount'), cls='text-right', nowrap=True)
            with tbody():
                for line in document.lines:
                    with tr():
                        td(line.product and line.product.render.code or '')
                        desc = '%s' % (line.product and line.product.render.name or '')
                        if line.raw.description:
                            desc += '<p>%s</p>' % line.render.description
                        td(raw(desc))
                        qty = '%s' % line.render.quantity
                        if line.unit:
                            qty += ' %s' % line.unit.render.symbol
                        td(qty, cls='text-right')
                        td(line.render.unit_price, cls='text-right')
                        td(line.render.amount, cls='text-right')
                with tr(cls='b-hide'):
                    td(colspan='5')
        return lines_table

    @classmethod
    def show_due_dates(cls, invoice, company):
        if not invoice.move or not invoice.move.lines:
            return raw('')
        due_table = table(id='due-dates', style='width:4cm;')
        with due_table:
            with thead():
                with tr():
                    th(cls.label('account.move.line',
                        'maturity_date'))
                    th(cls.label('account.move.line', 'amount'),
                        cls='text-right')
            with tbody(cls='border'):
                for line in invoice.html_lines_to_pay:
                    with tr():
                        td(line.render.maturity_date, cls='tex-right')
                        amount = line.raw.debit - line.raw.credit
                        formatted = html_render(
                            amount, digits=invoice.currency.raw.digits)
                        td('%s %s' % (formatted,
                            invoice.currency.render.symbol),
                            cls='text-right no-wrap')
        return due_table

    @classmethod
    def show_taxes(cls, invoice):
        if not invoice.taxes:
            return raw('')
        container = div()
        with container:
            div(strong(cls.label('account.invoice', 'taxes')),
                align='center')
            taxes_table = table(cls='condensed')
            with taxes_table:
                with thead():
                    th(cls.label('account.invoice.tax',
                        'description'))
                    th(cls.label('account.invoice.tax', 'base'),
                        cls='text-right')
                    th(cls.label('account.invoice.tax', 'amount'),
                        cls='text-right')
                with tbody(cls='border'):
                    for tax, value in invoice.raw.html_taxes.items():
                        with tr():
                            td(tax.render.description)
                            td('%s %s' % (value['base'],
                                invoice.currency.render.symbol),
                                cls='text-right')
                            td('%s %s' % (value['amount'],
                                invoice.currency.render.symbol),
                                cls='text-right')
                        if value.get('legal_notice'):
                            with tr():
                                with td(colspan='3'):
                                    strong('%s:' % cls.label(
                                        'account.invoice.tax', 'legal_notice'))
                                    raw(' %s' % value['legal_notice'])
        return container

    @classmethod
    def show_document_info(cls, record):
        title = _('Invoice')
        if record.raw.untaxed_amount < 0 and record.raw.type == 'out':
            title = _('Credit Note')
        if record.raw.state == 'validated':
            title = _('Proforma')
        document_date = (record.raw.invoice_date
            and record.render.invoice_date)
        label_date = cls.label(record.raw.__name__, 'invoice_date')
        container = div()
        with container:
            heading = title
            if record.raw.number:
                heading = '%s: %s' % (title, record.render.number)
            h1(heading, cls='document')
            if document_date:
                h2('%s: %s' % (label_date, document_date), cls='document')
            if record.raw.reference:
                h2('%s: %s' % (
                    cls.label(record.raw.__name__, 'reference'),
                    record.render.reference), cls='document')
        return container

    @classmethod
    def _tax_code(cls, record):
        if not hasattr(record.raw, 'aeat_qr_url'):
            return raw('')
        if not record.raw.aeat_qr_url:
            return raw('')
        container = div(style='text-align:center;')
        with container:
            p('QR Tributario:', style='margin:0;')
            img(
                src=cls.qrcode(record.raw.aeat_qr_url),
                style='width: 30mm; height: 30mm;')
            if 'ValidarQRNoVerifactu' not in record.raw.aeat_qr_url:
                p('VERI*FACTU', style='margin:0;')
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
    def show_payment_info(cls, document):
        return cls.common().show_payment_info(document)

    @classmethod
    def show_totals(cls, record):
        return cls.common().show_totals(record)

    @classmethod
    def show_logo(cls, record):
        company = record.company
        if company.render.logo:
            return img(cls='logo', src=company.render.logo)

    @classmethod
    def header(cls, action, data, records):
        record, = records
        company = record.company
        header = div()
        with header:
            if getattr(record.raw, 'aeat_qr_url', None):
                style(raw('.company_logo {\n    width: 15%;\n  }'))
            with header_tag(id='header'):
                with table():
                    with tr():
                        with td(cls='company_logo') as cell:
                            logo = cls.show_logo(record)
                            if logo:
                                cell.add(logo)
                        if getattr(record.raw, 'aeat_qr_url', None):
                            with td(style='width: 1%'):
                                cls._tax_code(record)
                        with td():
                            cls.show_document_info(record)
                    with tr():
                        with td(cls='party_info'):
                            cls.show_company_info(company)
                        if getattr(record.raw, 'aeat_qr_url', None):
                            td('', style='width: 1%')
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
        company = record.company
        last_footer = div()
        with last_footer:
            with div(id='last-footer', align='center'):
                with table(id='totals', cls='condensed'):
                    with tr():
                        with td():
                            cls.show_taxes(record)
                        with td(cls='right'):
                            cls.show_totals(record)
                    with tr():
                        with td():
                            cls.show_payment_info(record)
                        with td():
                            cls.show_due_dates(record, company)
        return last_footer

    @classmethod
    def body(cls, action, data, records):
        record, = records
        container = div()
        with container:
            container.add(cls.show_invoice_lines(record))
            if record.raw.comment:
                h4(cls.label('account.invoice', 'comment'))
                p(raw(record.render.comment))

        return container


class InvoiceReport(InvoiceReportMixin):
    __name__ = 'account.invoice'
