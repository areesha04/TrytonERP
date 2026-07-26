import unittest
from decimal import Decimal

from proteus import Model, Report
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear, create_tax,
                                                 create_tax_code, get_accounts)
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
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

        # Install modules
        config = activate_modules(['html_report', 'account_invoice',
                'account_payment_type', 'account_bank',
                'account_invoice_stock'])

        # Create company
        _ = create_company()
        company = get_company()
        tax_identifier = company.party.identifiers.new()
        tax_identifier.type = 'eu_vat'
        tax_identifier.code = 'BE0897290877'
        company.party.save()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']
        account_cash = accounts['cash']

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()
        invoice_base_code = create_tax_code(tax, 'base', 'invoice')
        invoice_base_code.save()
        invoice_tax_code = create_tax_code(tax, 'tax', 'invoice')
        invoice_tax_code.save()
        credit_note_base_code = create_tax_code(tax, 'base', 'credit')
        credit_note_base_code.save()
        credit_note_tax_code = create_tax_code(tax, 'tax', 'credit')
        credit_note_tax_code.save()

        # Create payment method
        Journal = Model.get('account.journal')
        PaymentMethod = Model.get('account.invoice.payment.method')
        journal_cash, = Journal.find([('type', '=', 'cash')])
        payment_method = PaymentMethod()
        payment_method.name = 'Cash'
        payment_method.journal = journal_cash
        payment_method.credit_account = account_cash
        payment_method.debit_account = account_cash
        payment_method.save()

        # Create Write Off method
        WriteOff = Model.get('account.move.reconcile.write_off')
        journal_writeoff = Journal(name='Write-Off', type='write-off')
        journal_writeoff.save()
        writeoff_method = WriteOff()
        writeoff_method.name = 'Rate loss'
        writeoff_method.journal = journal_writeoff
        writeoff_method.credit_account = expense
        writeoff_method.debit_account = expense
        writeoff_method.save()

        # Create party
        Party = Model.get('party.party')
        party = Party(name='Party')
        party.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(tax)
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'service'
        template.list_price = Decimal('40')
        template.account_category = account_category
        template.save()
        product, = template.products

        # Create payment term
        PaymentTerm = Model.get('account.invoice.payment_term')
        payment_term = PaymentTerm(name='Term')
        line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
        delta, = line.relativedeltas
        delta.days = 20
        line = payment_term.lines.new(type='remainder')
        delta = line.relativedeltas.new(days=40)
        payment_term.save()

        # Create invoice
        Invoice = Model.get('account.invoice')
        InvoiceLine = Model.get('account.invoice.line')
        invoice = Invoice(type='out')
        invoice.party = party
        invoice.payment_term = payment_term
        line = InvoiceLine()
        invoice.lines.append(line)
        line.product = product
        line.quantity = 5
        line.unit_price = Decimal('40')
        line = InvoiceLine()
        invoice.lines.append(line)
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal(20)
        self.assertEqual(invoice.untaxed_amount, Decimal('220.00'))
        self.assertEqual(invoice.tax_amount, Decimal('20.00'))
        self.assertEqual(invoice.total_amount, Decimal('240.00'))
        invoice.save()

        # Render report
        InvoiceReport = Report('account.invoice')
        oext, _, _, _ = InvoiceReport.execute([invoice])
        self.assertEqual(oext, 'pdf')
        self.assertEqual(invoice.invoice_report_cache, None)
        self.assertEqual(invoice.invoice_report_format, None)

        # Post invoice
        invoice.click('post')
        self.assertEqual(invoice.state, 'posted')
        self.assertNotEqual(invoice.invoice_report_cache, None)
        self.assertEqual(invoice.invoice_report_format, 'pdf')
        oext, _, _, _ = InvoiceReport.execute([invoice])
        self.assertEqual(oext, 'pdf')

        # Dissable invoice cache
        Configuration = Model.get('account.configuration')
        configuration = Configuration(1)
        configuration.use_invoice_report_cache = False
        configuration.save()

        # Duplicate invoice
        invoice2, = Invoice.copy([invoice], config.context)
        invoice2 = Invoice(invoice2)

        # Post invoice
        invoice2.click('post')
        self.assertEqual(invoice2.state, 'posted')
        self.assertEqual(invoice2.invoice_report_cache, None)
        self.assertNotEqual(invoice2.invoice_report_format, 'pdf')

    def test_invoice_report_manual_tax_without_account_tax(self):
        activate_modules(['html_report', 'account_invoice',
                'account_payment_type', 'account_bank',
                'account_invoice_stock'])

        _ = create_company()
        company = get_company()

        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']

        Party = Model.get('party.party')
        party = Party(name='Party')
        party.save()

        Invoice = Model.get('account.invoice')
        InvoiceLine = Model.get('account.invoice.line')
        invoice = Invoice(type='out')
        invoice.party = party
        line = InvoiceLine()
        invoice.lines.append(line)
        line.account = revenue
        line.description = 'Test'
        line.quantity = 1
        line.unit_price = Decimal('100')

        tax_line = invoice.taxes.new()
        tax_line.description = 'Manual Tax'
        tax_line.account = accounts['tax']
        tax_line.base = Decimal('100')
        tax_line.amount = Decimal('10')

        invoice.save()
        self.assertIsNone(tax_line.tax)
        self.assertEqual(invoice.tax_amount, Decimal('10.00'))

        InvoiceReport = Report('account.invoice')
        oext, _, _, _ = InvoiceReport.execute([invoice])
        self.assertEqual(oext, 'pdf')
