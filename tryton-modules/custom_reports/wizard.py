from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder, Eval
from trytond.wsgi import app
from werkzeug.wrappers import Response
from trytond.transaction import Transaction
from weasyprint import HTML as WeasyHTML

from .general_ledger import GeneralLedgerReport
from .cash_book import CashBookReport
from .expense_report import ExpenseReport
from .vendor_ledger import VendorLedgerReport

# ==========================================
# 0. CUSTOM WEB CONTROLLER (Forces PDF Preview)
# ==========================================
@app.route('/<database_name>/custom_reports/preview/<int:attachment_id>', methods=['GET'])
def preview_pdf(request, database_name, attachment_id):
    pool = Pool(database_name)
    with Transaction().start(database_name, 0, readonly=True):
        Attachment = pool.get('ir.attachment')
        attachment = Attachment(attachment_id)
        file_data = attachment.data
        filename = attachment.name

    response = Response(file_data, mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# ==========================================
# 1. WIZARD START MODEL WITH DYNAMIC FIELDS
# ==========================================
class PrintReportRCStart(ModelView):
    __name__ = 'account.print_report_rc.start'
    
    report_type = fields.Selection([
        ('general_ledger', 'General Ledger (COA)'),
        ('cash_book', 'Cash Book'),
        ('expense_report', 'Expense Report'),
        ('vendor_ledger', 'Vendor Ledger'),
    ], 'Report Type', required=True)
    
    account = fields.Many2One('account.account', 'Account',
        states={
            'invisible': Eval('report_type').in_(['vendor_ledger', 'expense_report']),
            'required': Eval('report_type').in_(['general_ledger', 'cash_book']),
        },
        depends=['report_type'])

    # REMOVED the 'required' state so you can leave it empty for ALL parties
    party = fields.Many2One('party.party', 'Vendor / Party',
        states={
            'invisible': Eval('report_type') != 'vendor_ledger',
        },
        depends=['report_type'])
        
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)

    @staticmethod
    def default_report_type():
        return 'general_ledger'


# ==========================================
# 2. WIZARD CONTROLLER
# ==========================================
class PrintReportRC(Wizard):
    __name__ = 'account.print_report_rc'
    
    start = StateView('account.print_report_rc.start',
        'custom_reports.print_report_rc_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('View on Screen', 'view_data', 'tryton-list'), 
            Button('Open PDF', 'preview_tab', 'tryton-print', default=True),
        ])
    
    view_data = StateAction('custom_reports.act_view_report_data')
    preview_tab = StateAction('custom_reports.act_preview_url')

    def do_view_data(self, action):
        pool = Pool()
        Account = pool.get('account.account')
        domain = [
            ('date', '>=', self.start.start_date),
            ('date', '<=', self.start.end_date),
        ]
        if self.start.report_type == 'vendor_ledger' and self.start.party:
            domain.append(('party', '=', self.start.party.id))
            acc_name = self.start.party.name
        elif self.start.report_type == 'expense_report':
            expense_accounts = Account.search([('type.expense', '=', True)])
            expense_ids = [acc.id for acc in expense_accounts]
            domain.append(('account', 'in', expense_ids))
            acc_name = 'All Expense Accounts'
        elif self.start.report_type == 'cash_book':
            cash_accounts = Account.search([('name', 'ilike', 'cash')], limit=1)
            if not cash_accounts:
                cash_accounts = Account.search([('code', 'like', '10%')], limit=1)
            account_id = cash_accounts[0].id if cash_accounts else None
            if account_id:
                domain.append(('account', '=', account_id))
            acc_name = 'Cash Book'
        elif self.start.account:
            domain.append(('account', '=', self.start.account.id))
            acc_name = self.start.account.name
        else:
            acc_name = 'Report'

        action['pyson_domain'] = PYSONEncoder().encode(domain)
        action['pyson_context'] = PYSONEncoder().encode({
            'rc_report_type': self.start.report_type,
            'rc_account_id': self.start.account.id if self.start.account else None,
            'rc_party_id': self.start.party.id if self.start.party else None,
            'rc_start_date': self.start.start_date,
            'rc_end_date': self.start.end_date,
        })
        
        action['name'] = f"{self.start.report_type.replace('_', ' ').title()} - {acc_name}"
        return action, {}

    def do_preview_tab(self, action):
        pool = Pool()
        Account = pool.get('account.account')
        Attachment = pool.get('ir.attachment')
        
        account_id = self.start.account.id if self.start.account else None
        party_id = self.start.party.id if self.start.party else None

        if self.start.report_type == 'cash_book' and not account_id:
            cash_accounts = Account.search([('name', 'ilike', 'cash')], limit=1)
            if not cash_accounts:
                cash_accounts = Account.search([('code', 'like', '10%')], limit=1)
            account_id = cash_accounts[0].id if cash_accounts else None

        data = {
            'account_id': account_id,
            'party_id': party_id,
            'start_date': self.start.start_date,
            'end_date': self.start.end_date,
            'company_name': 'Rays Creation'
        }
        
        if self.start.report_type == 'cash_book':
            account = Account(account_id) if account_id else None
            html_content = CashBookReport.get_html([account] if account else [], data)
            filename = "cash_book.pdf"
        elif self.start.report_type == 'vendor_ledger':
            html_content = VendorLedgerReport.get_html([], data)
            filename = f"vendor_ledger_{party_id}.pdf"
        elif self.start.report_type == 'expense_report':
            html_content = ExpenseReport.get_html([], data)
            filename = "expense_report.pdf"
        else:
            account = Account(account_id) if account_id else None
            html_content = GeneralLedgerReport.get_html([account] if account else [], data)
            filename = f"general_ledger_{account.code if account else 'general'}.pdf"
            
        pdf_bytes = WeasyHTML(string=html_content).write_pdf()
        resource_ref = f"account.account,{account_id}" if account_id else f"res.user,{Transaction().user}"

        attachment = Attachment.create([{
            'name': filename,
            'type': 'data',
            'data': pdf_bytes,
            'resource': resource_ref,
        }])[0]
        
        db_name = Transaction().database.name
        action['url'] = f"/{db_name}/custom_reports/preview/{attachment.id}"
        
        return action, {}


# ==========================================
# 3. DIRECT PDF DOWNLOAD WIZARD
# ==========================================
class DirectPDFWizard(Wizard):
    'Invisible Wizard for Direct PDF Download'
    __name__ = 'account.move.line.direct_pdf_wizard'

    start_state = 'generate'
    generate = StateAction('custom_reports.act_preview_url')

    def do_generate(self, action):
        pool = Pool()
        Account = pool.get('account.account')
        Attachment = pool.get('ir.attachment')
        context = Transaction().context
        
        report_type = context.get('rc_report_type', 'general_ledger')
        account_id = context.get('rc_account_id')
        party_id = context.get('rc_party_id')
        start_date = context.get('rc_start_date')
        end_date = context.get('rc_end_date')

        if not account_id and not party_id and report_type not in ['cash_book', 'expense_report']:
            return action, {}
            
        account = Account(account_id) if account_id else None
        report_data = {
            'account_id': account_id,
            'party_id': party_id,
            'start_date': start_date,
            'end_date': end_date,
            'company_name': 'Rays Creation'
        }
        
        if report_type == 'cash_book':
            html_content = CashBookReport.get_html([account] if account else [], report_data)
            filename = "cash_book.pdf"
        elif report_type == 'vendor_ledger':
            html_content = VendorLedgerReport.get_html([], report_data)
            filename = f"vendor_ledger_{party_id}.pdf"
        elif report_type == 'expense_report':
            html_content = ExpenseReport.get_html([], report_data)
            filename = "expense_report.pdf"
        else:
            html_content = GeneralLedgerReport.get_html([account] if account else [], report_data)
            filename = f"general_ledger_{account.code if account else 'general'}.pdf"
            
        pdf_bytes = WeasyHTML(string=html_content).write_pdf()
        resource_ref = f"account.account,{account_id}" if account_id else f"res.user,{Transaction().user}"

        attachment = Attachment.create([{
            'name': filename,
            'type': 'data',
            'data': pdf_bytes,
            'resource': resource_ref,
        }])[0]
        
        db_name = Transaction().database.name
        action['url'] = f"/{db_name}/custom_reports/preview/{attachment.id}"
        
        return action, {}