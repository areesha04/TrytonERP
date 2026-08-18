from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import PYSONEncoder, Eval
from trytond.wsgi import app
from werkzeug.wrappers import Response
from trytond.transaction import Transaction
from weasyprint import HTML as WeasyHTML

# === NEW IMPORTS FOR MOVE REPORT ===
from trytond.modules.html_report.html_report import HTMLReport
import dominate.tags as tags
from decimal import Decimal

from .general_ledger import GeneralLedgerReport
from .cash_book import CashBookReport
from .expense_report import ExpenseReport
from .vendor_ledger import VendorLedgerReport
from .advance_payment_report import VendorAdvanceDepositReport
from trytond.exceptions import UserError
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


# =========================================================
# 1. ACCOUNT MOVE / TRANSFERS / PAYMENTS (NEW UNIFIED LOGIC)
# =========================================================
class AccountMoveCustomReport(HTMLReport):
    __name__ = 'account.move.custom_report'

    @classmethod
    def get_html(cls, records, data):
        # Retrieve the custom title from the wizard, default to JOURNAL ENTRY
        report_title = data.get('report_title', 'JOURNAL ENTRY')
        
        doc = tags.div(style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 12px; color: #333; padding: 20px 30px; position: relative; z-index: 1; max-width: 800px; margin: auto;")
        
        with doc:
            for move in records:
                with tags.table(style="width: 100%; margin-bottom: 25px; border-collapse: collapse;"):
                    with tags.tr():
                        with tags.td(style="width: 50%; vertical-align: bottom;"):
                            # Inject dynamic title here
                            tags.h2(report_title, style="margin: 0; font-size: 20px; color: #2980b9; text-transform: uppercase; letter-spacing: 1.5px;")
                            tags.div("ACCOUNT MOVE DETAILS", style="font-size: 11px; color: #7f8c8d; margin-top: 5px; font-weight: bold;")
                        with tags.td(style="width: 50%; text-align: right;"):
                            with tags.table(style="float: right; border-collapse: collapse; text-align: right; font-size: 12px;"):
                                with tags.tr():
                                    tags.td(tags.b("Date:"), style="padding: 2px 10px 2px 0; color: #7f8c8d;")
                                    tags.td(str(move.date or 'N/A'), style="padding: 2px 0;")
                                with tags.tr():
                                    tags.td(tags.b("Move No:"), style="padding: 2px 10px 2px 0; color: #7f8c8d;")
                                    tags.td(move.number or 'Draft', style="padding: 2px 0; font-weight: bold; color: #2c3e50;")
                                with tags.tr():
                                    tags.td(tags.b("Journal:"), style="padding: 2px 10px 2px 0; color: #7f8c8d;")
                                    tags.td(move.journal.name if move.journal else 'N/A', style="padding: 2px 0;")
                                if move.description:
                                    with tags.tr():
                                        tags.td(tags.b("Description:"), style="padding: 2px 10px 2px 0; color: #7f8c8d;")
                                        tags.td(move.description, style="padding: 2px 0;")

                with tags.table(style="width: 100%; border-collapse: collapse; margin-bottom: 25px;"):
                    with tags.thead():
                        with tags.tr(style="background-color: #2c3e50; color: #ffffff; text-align: left;"):
                            tags.th("Account", style="padding: 8px; font-weight: normal;")
                            tags.th("Party", style="padding: 8px; font-weight: normal;")
                            tags.th("Description", style="padding: 8px; font-weight: normal;")
                            tags.th("Debit", style="padding: 8px; font-weight: normal; text-align: right; width: 100px;")
                            tags.th("Credit", style="padding: 8px; font-weight: normal; text-align: right; width: 100px;")
                    
                    with tags.tbody():
                        total_debit = Decimal('0.0')
                        total_credit = Decimal('0.0')
                        
                        for index, line in enumerate(move.lines):
                            bg_color = "#f9f9f9" if index % 2 != 0 else "#ffffff"
                            total_debit += line.debit or Decimal('0.0')
                            total_credit += line.credit or Decimal('0.0')
                            
                            account_str = f"{line.account.code} - {line.account.name}" if line.account else ""
                            if line.party:
                                party_str = line.party.name
                            elif line.custom_party:
                                party_str = line.custom_party.name
                            else:
                                party_str = ""
                            
                            
                            with tags.tr(style=f"background-color: {bg_color}; border-bottom: 1px solid #ecf0f1;"):
                                tags.td(account_str, style="padding: 8px; color: #2c3e50;")
                                tags.td(party_str, style="padding: 8px;")
                                tags.td(line.description or '', style="padding: 8px;")
                                tags.td(f"{line.debit:,.2f}" if line.debit else "", style="padding: 8px; text-align: right;")
                                tags.td(f"{line.credit:,.2f}" if line.credit else "", style="padding: 8px; text-align: right;")

                        with tags.tr(style="background-color: #f4f6f7; font-weight: bold; border-top: 2px solid #2c3e50;"):
                            tags.td("TOTALS", colspan="3", style="padding: 10px; text-align: right; color: #7f8c8d;")
                            tags.td(f"{total_debit:,.2f}", style="padding: 10px; text-align: right; color: #2c3e50;")
                            tags.td(f"{total_credit:,.2f}", style="padding: 10px; text-align: right; color: #2c3e50;")

        return doc.render()

class PreviewUniversalMoveWizard(Wizard):
    'Invisible Wizard for Direct PDF Download across multiple menus'
    __name__ = 'account.move.preview_universal_wizard'

    start_state = 'generate'
    generate = StateAction('custom_reports.act_preview_url') 

    def do_generate(self, action):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        context = Transaction().context
        
        active_ids = context.get('active_ids')
        active_model = context.get('active_model')
        
        if not active_ids or not active_model:
            return action, {}
            
        Model = pool.get(active_model)
        records = Model.browse(active_ids)
        record = records[0] 
        
        # 1. Detect active model, assign title, and isolate the Account Move
        if active_model == 'account.move':
            move = record
            report_title = "JOURNAL ENTRY"
            
        elif active_model == 'custom.account.quick_entry':
            move = record.move
            report_title = "FUNDS TRANSFER"
            if not move:
                # Raises a clean window with a single OK button and halts execution
                raise UserError("Cannot print preview! No Account Move has been generated yet. Please post the entry first.")
                
        elif active_model == 'custom.account.multi_expense':
            move = record.move
            report_title = "BANK/CASH PAYMENT"
            if not move:
                # Raises a clean window with a single OK button and halts execution
                raise UserError("Cannot print preview! No Account Move has been generated yet. Please post the entry first.")
                
        else:
            return action, {}

        # 2. Generate PDF and pass the dynamic title
        report_data = {'report_title': report_title}
        html_content = AccountMoveCustomReport.get_html([move], report_data)
        pdf_bytes = WeasyHTML(string=html_content).write_pdf()
        
        # Format filename cleanly
        safe_title = report_title.replace(" ", "_").replace("/", "_")
        filename = f"{safe_title}_{move.number or move.id}.pdf"
        
        # 3. File management logic
        existing_attachments = Attachment.search([
            ('resource', '=', f"account.move,{move.id}"),
            ('name', '=', filename)
        ])
        
        if existing_attachments:
            attachment = existing_attachments[0]
            Attachment.write([attachment], {'data': pdf_bytes})
        else:
            attachment = Attachment.create([{
                'name': filename,
                'type': 'data',
                'data': pdf_bytes,
                'resource': f"account.move,{move.id}",
            }])[0]
        
        # 4. Open in new tab using existing web controller
        db_name = Transaction().database.name
        action['url'] = f"/{db_name}/custom_reports/preview/{attachment.id}"
        
        return action, {}


# ==========================================
# 2. WIZARD START MODEL WITH DYNAMIC FIELDS
# ==========================================
class PrintReportRCStart(ModelView):
    __name__ = 'account.print_report_rc.start'
    
    report_type = fields.Selection([
        ('general_ledger', 'General Ledger (COA)'),
        ('cash_book', 'Cash Book'),
        ('expense_report', 'Expense Report'),
        ('vendor_ledger', 'Vendor Ledger'),
        ('vendor_advance', 'Vendor Advance & Deposit'),
    ], 'Report Type', required=True)
    
    account = fields.Many2One('account.account', 'Account',
        states={
            'invisible': Eval('report_type').in_(['vendor_ledger', 'expense_report', 'vendor_advance']),
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
# 3. WIZARD CONTROLLER FOR FINANCIAL REPORTS
# ==========================================
class PrintReportRC(Wizard):
    __name__ = 'account.print_report_rc'
    
    start = StateView('account.print_report_rc.start',
        'custom_reports.print_report_rc_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
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
        elif self.start.report_type == 'vendor_advance': # <-- ADDED LOGIC FOR SCREEN VIEW
            if self.start.party:
                domain.append(('party', '=', self.start.party.id))
                acc_name = self.start.party.name
            else:
                acc_name = 'All Vendors'
        elif self.start.report_type == 'expense_report':
            expense_accounts = Account.search(['OR', 
                ('code', 'like', '5%'), 
                ('code', 'like', '6%')
            ])
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
        MoveLine = pool.get('account.move.line') 

        account_id = self.start.account.id if self.start.account else None
        party_id = self.start.party.id if self.start.party else None
        report_type = self.start.report_type
        start_date = self.start.start_date
        end_date = self.start.end_date

        # 1. First, figure out the account_id if it's missing
        if report_type == 'cash_book' and not account_id:
            cash_accounts = Account.search([('name', 'ilike', 'cash')], limit=1)
            if not cash_accounts:
                cash_accounts = Account.search([('code', 'like', '10%')], limit=1)
            account_id = cash_accounts[0].id if cash_accounts else None

        # 2. THEN, create the data dictionary using that account_id
        data = {
            'account_id': account_id,
            'party_id': party_id,
            'start_date': start_date,
            'end_date': end_date,
            'company_name': 'RAYS Creations'
        }
        
        # 3. THEN, calculate the opening balance and attach it to data
        if report_type == 'cash_book' and account_id and start_date:
            historical_lines = MoveLine.search([
                ('account', '=', account_id),
                ('date', '<', start_date)
            ])
            total_debit = sum((line.debit for line in historical_lines if line.debit), Decimal('0.00'))
            total_credit = sum((line.credit for line in historical_lines if line.credit), Decimal('0.00'))
            data['opening_balance'] = total_debit - total_credit
        
        # 4. Finally, generate the report based on the type
        if report_type == 'cash_book':
            account = Account(account_id) if account_id else None
            html_content = CashBookReport.get_html([account] if account else [], data)
            filename = "cash_book.pdf"
        elif report_type == 'vendor_ledger':
            html_content = VendorLedgerReport.get_html([], data)
            filename = f"vendor_ledger_{party_id}.pdf"
        elif report_type == 'vendor_advance':
            data['supplier_id'] = party_id
            html_content = VendorAdvanceDepositReport.get_html([], data)
            filename = f"vendor_advance_{party_id or 'all'}.pdf"
        elif report_type == 'expense_report':
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
# 4. DIRECT PDF DOWNLOAD WIZARD
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
        MoveLine = pool.get('account.move.line') 
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
            'company_name': 'RAYS Creations'
        }

        if report_type == 'cash_book' and account_id and start_date:
            historical_lines = MoveLine.search([
                ('account', '=', account_id),
                ('date', '<', start_date)
            ])
            total_debit = sum((line.debit for line in historical_lines if line.debit), Decimal('0.00'))
            total_credit = sum((line.credit for line in historical_lines if line.credit), Decimal('0.00'))
            report_data['opening_balance'] = total_debit - total_credit
        
        if report_type == 'cash_book':
            html_content = CashBookReport.get_html([account] if account else [], report_data)
            filename = "cash_book.pdf"
        elif report_type == 'vendor_ledger':
            html_content = VendorLedgerReport.get_html([], report_data)
            filename = f"vendor_ledger_{party_id}.pdf"
        elif report_type == 'vendor_advance': 
            report_data['supplier_id'] = party_id
            html_content = VendorAdvanceDepositReport.get_html([], report_data)
            filename = f"vendor_advance_{party_id or 'all'}.pdf"
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