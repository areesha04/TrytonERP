from trytond.pool import Pool
from . import general_ledger
from . import cash_book
from . import expense_report
from . import vendor_ledger
from . import wizard
from . import supplier_invoice
from .supplier_invoice import SupplierInvoiceCustomReport, PreviewInvoiceWizard
def register():
    Pool.register(
        wizard.PrintReportRCStart,
        module='custom_reports',
        type_='model',
    )
    Pool.register(
        wizard.PrintReportRC,
        wizard.DirectPDFWizard,
        supplier_invoice.PreviewInvoiceWizard,
        module='custom_reports',
        type_='wizard',
    )
    Pool.register(
        general_ledger.GeneralLedgerReport,
        cash_book.CashBookReport,
        expense_report.ExpenseReport,
        vendor_ledger.VendorLedgerReport,
        module='custom_reports',
        type_='report',
    )