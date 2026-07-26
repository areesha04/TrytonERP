from decimal import Decimal
import dominate.tags as tags
from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, StateReport, Button
from trytond.modules.html_report.html_report import HTMLReport
from trytond.pyson import PYSONEncoder 
from trytond.wsgi import app
from werkzeug.wrappers import Response
from trytond.transaction import Transaction
from weasyprint import HTML as WeasyHTML
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

    # Set back to application/pdf so the browser loads the PDF viewer
    response = Response(file_data, mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    return response

# ==========================================
# 1. GENERAL LEDGER REPORT ENGINE
# ==========================================

class GeneralLedgerReport(HTMLReport):
    __name__ = 'account.general_ledger_custom'

    @classmethod
    def render(cls, action, report_context, lang=None):
        records = report_context.get('records', [])
        data = report_context.get('data', {})
        return cls.get_html(records, data)

    @classmethod
    def get_html(cls, records, data):
        pool = Pool()
        Account = pool.get('account.account')
        MoveLine = pool.get('account.move.line')

        if not records and 'account_id' in data:
            records = Account.browse([data['account_id']])
            
        start_date = data.get('start_date', '01-01-2024')
        end_date = data.get('end_date', '31-12-2024')
        company_name = data.get('company_name', 'Rays Creation')

        doc = tags.div(style="font-family: Arial, sans-serif; font-size: 11px; color: #000; padding: 15px;")
        with doc:
            tags.h1("GENERAL LEDGER", style="margin: 0; font-size: 20px; font-weight: bold; text-decoration: underline;")
            tags.h3(company_name, style="margin: 5px 0 20px 0; font-size: 16px; font-weight: bold;")

            for account in records:
                start_balance = Decimal('1027816.84')
                running_balance = start_balance

                with tags.table(style="width: 100%; margin-bottom: 10px; border-collapse: collapse;"):
                    with tags.tr():
                        with tags.td(style="font-weight: bold; font-size: 13px; vertical-align: bottom;"):
                            tags.span(f"Account : {account.name} - {account.code}")
                        with tags.td(style="text-align: right; width: 200px;"):
                            with tags.table(style="width: 100%; border-collapse: collapse; border: 1px dotted #000; font-size: 11px;"):
                                with tags.tr():
                                    tags.td("From", style="border: 1px dotted #000; padding: 2px 6px; font-weight: bold; text-align: center;")
                                    tags.td(str(start_date), style="border: 1px dotted #000; padding: 2px 6px; text-align: center;")
                                with tags.tr():
                                    tags.td("To", style="border: 1px dotted #000; padding: 2px 6px; font-weight: bold; text-align: center;")
                                    tags.td(str(end_date), style="border: 1px dotted #000; padding: 2px 6px; text-align: center;")

                with tags.table(style="width: 100%; border-collapse: collapse; border: 1px solid #000; margin-bottom: 30px;"):
                    with tags.thead():
                        with tags.tr(style="border-bottom: 1px solid #000; font-weight: bold; text-align: center; background-color: #f2f2f2;"):
                            tags.th("Date", style="border: 1px dotted #000; padding: 5px; width: 80px;")
                            tags.th("Voucher No", style="border: 1px dotted #000; padding: 5px; width: 90px;")
                            tags.th("Invoice No", style="border: 1px dotted #000; padding: 5px; width: 100px;")
                            tags.th("Doc Type", style="border: 1px dotted #000; padding: 5px; width: 110px;")
                            tags.th("Business Partner", style="border: 1px dotted #000; padding: 5px;")
                            tags.th("Description", style="border: 1px dotted #000; padding: 5px;")
                            tags.th("Debit", style="border: 1px dotted #000; padding: 5px; width: 90px;")
                            tags.th("Credit", style="border: 1px dotted #000; padding: 5px; width: 90px;")
                            tags.th("Balance", style="border: 1px dotted #000; padding: 5px; width: 100px;")

                    with tags.tbody():
                        with tags.tr():
                            tags.td(str(start_date), style="border: 1px dotted #000; padding: 4px; text-align: center;")
                            tags.td("", style="border: 1px dotted #000; padding: 4px;")
                            tags.td("", style="border: 1px dotted #000; padding: 4px;")
                            tags.td("", style="border: 1px dotted #000; padding: 4px;")
                            tags.td("", style="border: 1px dotted #000; padding: 4px;")
                            tags.td("Opening Balance", style="border: 1px dotted #000; padding: 4px; font-weight: bold;")
                            tags.td("", style="border: 1px dotted #000; padding: 4px;")
                            tags.td("", style="border: 1px dotted #000; padding: 4px;")
                            tags.td(f"{start_balance:,.2f}", style="border: 1px dotted #000; padding: 4px; text-align: right; font-weight: bold;")

                        move_lines = MoveLine.search([('account', '=', account.id)], order=[('date', 'ASC'), ('id', 'ASC')])

                        for line in move_lines:
                            debit = line.debit or Decimal('0.00')
                            credit = line.credit or Decimal('0.00')
                            running_balance += (debit - credit)

                            with tags.tr():
                                line_date = line.date.strftime('%d-%m-%Y') if line.date else ''
                                tags.td(line_date, style="border: 1px dotted #000; padding: 4px; text-align: center;")
                                
                                voucher_no = line.move.number if line.move and line.move.number else ''
                                tags.td(voucher_no, style="border: 1px dotted #000; padding: 4px; text-align: center;")
                                
                                invoice_no = ''
                                if line.move and line.move.origin:
                                    origin = line.move.origin
                                    invoice_no = getattr(origin, 'number', getattr(origin, 'rec_name', ''))
                                tags.td(str(invoice_no), style="border: 1px dotted #000; padding: 4px; text-align: center;")
                                
                                journal_name = line.journal.name if line.journal and line.journal.name else ''
                                tags.td(journal_name, style="border: 1px dotted #000; padding: 4px;")
                                
                                partner_name = line.party.name if line.party and line.party.name else 'Standard'
                                tags.td(partner_name, style="border: 1px dotted #000; padding: 4px;")
                                
                                desc = line.description or (line.move.description if line.move else '')
                                tags.td(str(desc or ''), style="border: 1px dotted #000; padding: 4px;")
                                
                                tags.td(f"{debit:,.2f}" if debit else "", style="border: 1px dotted #000; padding: 4px; text-align: right;")
                                tags.td(f"{credit:,.2f}" if credit else "", style="border: 1px dotted #000; padding: 4px; text-align: right;")
                                tags.td(f"{running_balance:,.2f}", style="border: 1px dotted #000; padding: 4px; text-align: right;")

        return doc.render()


# ==========================================
# 2. CASH BOOK REPORT ENGINE
# ==========================================

class CashBookReport(HTMLReport):
    __name__ = 'account.cash_book_custom'

    @classmethod
    def render(cls, action, report_context, lang=None):
        records = report_context.get('records', [])
        data = report_context.get('data', {})
        return cls.get_html(records, data)

    @classmethod
    def get_html(cls, records, data):
        pool = Pool()
        Account = pool.get('account.account')
        MoveLine = pool.get('account.move.line')

        if not records and 'account_id' in data:
            records = Account.browse([data['account_id']])

        doc = tags.div(style="font-family: Arial, sans-serif; font-size: 10px; padding: 10px;")
        with doc:
            tags.h2("RAYS CREATION", style="text-align: center; margin: 0; font-size: 16px;")
            tags.h3("CASH BOOK", style="text-align: center; margin: 0 0 15px 0; font-size: 14px;")

            for account in records:
                move_lines = MoveLine.search([('account', '=', account.id)], order=[('date', 'ASC')])
                receipts = [l for l in move_lines if l.debit and l.debit > 0]
                payments = [l for l in move_lines if l.credit and l.credit > 0]

                with tags.div(style="display: flex; width: 100%; border: 1px solid #000;"):
                    # RECEIPTS (Left)
                    with tags.div(style="width: 50%; border-right: 1px solid #000;"):
                        with tags.table(style="width: 100%; border-collapse: collapse;"):
                            with tags.thead():
                                with tags.tr(style="background-color: #e6e6fa; border-bottom: 1px solid #000;"):
                                    tags.th("RECEIPTS", colspan="5", style="text-align: center; padding: 4px;")
                                with tags.tr(style="background-color: #ffffe0; border-bottom: 1px solid #000; font-weight: bold;"):
                                    tags.th("Date", style="border-right: 1px dotted #000; padding: 3px;")
                                    tags.th("COA", style="border-right: 1px dotted #000; padding: 3px;")
                                    tags.th("V#", style="border-right: 1px dotted #000; padding: 3px;")
                                    tags.th("Description", style="border-right: 1px dotted #000; padding: 3px;")
                                    tags.th("Amount", style="padding: 3px;")
                            with tags.tbody():
                                for rec in receipts:
                                    co_name = ""
                                    if rec.move and rec.move.lines:
                                        for s_line in rec.move.lines:
                                            if s_line.id != rec.id:
                                                co_name = s_line.account.name
                                                break
                                    with tags.tr(style="border-bottom: 1px dotted #ccc;"):
                                        tags.td(str(rec.date or ''), style="border-right: 1px dotted #000; padding: 3px; text-align: center;")
                                        tags.td(co_name, style="border-right: 1px dotted #000; padding: 3px;")
                                        tags.td(rec.move.number if rec.move else '', style="border-right: 1px dotted #000; padding: 3px; text-align: center;")
                                        tags.td(rec.description or '', style="border-right: 1px dotted #000; padding: 3px;")
                                        tags.td(f"{rec.debit:,.2f}", style="padding: 3px; text-align: right;")

                    # PAYMENTS (Right)
                    with tags.div(style="width: 50%;"):
                        with tags.table(style="width: 100%; border-collapse: collapse;"):
                            with tags.thead():
                                with tags.tr(style="background-color: #e6e6fa; border-bottom: 1px solid #000;"):
                                    tags.th("PAYMENTS", colspan="5", style="text-align: center; padding: 4px;")
                                with tags.tr(style="background-color: #ffffe0; border-bottom: 1px solid #000; font-weight: bold;"):
                                    tags.th("Date", style="border-right: 1px dotted #000; padding: 3px;")
                                    tags.th("COA", style="border-right: 1px dotted #000; padding: 3px;")
                                    tags.th("V#", style="border-right: 1px dotted #000; padding: 3px;")
                                    tags.th("Description", style="border-right: 1px dotted #000; padding: 3px;")
                                    tags.th("Amount", style="padding: 3px;")
                            with tags.tbody():
                                for pay in payments:
                                    co_name = ""
                                    if pay.move and pay.move.lines:
                                        for s_line in pay.move.lines:
                                            if s_line.id != pay.id:
                                                co_name = s_line.account.name
                                                break
                                    with tags.tr(style="border-bottom: 1px dotted #ccc;"):
                                        tags.td(str(pay.date or ''), style="border-right: 1px dotted #000; padding: 3px; text-align: center;")
                                        tags.td(co_name, style="border-right: 1px dotted #000; padding: 3px;")
                                        tags.td(pay.move.number if pay.move else '', style="border-right: 1px dotted #000; padding: 3px; text-align: center;")
                                        tags.td(pay.description or '', style="border-right: 1px dotted #000; padding: 3px;")
                                        tags.td(f"{pay.credit:,.2f}", style="padding: 3px; text-align: right;")

        return doc.render()


# ==========================================
# 3. WIZARD CONTROLLER (Opens in New Tab)
# ==========================================

class PrintReportRCStart(ModelView):
    __name__ = 'account.print_report_rc.start'
    
    report_type = fields.Selection([
        ('general_ledger', 'General Ledger'),
        ('cash_book', 'Cash Book'),
    ], 'Report Type', required=True)
    
    account = fields.Many2One('account.account', 'Account', required=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)

    @staticmethod
    def default_report_type():
        return 'general_ledger'


class PrintReportRC(Wizard):
    __name__ = 'account.print_report_rc'
    
    start = StateView('account.print_report_rc.start',
        'custom_reports.print_report_rc_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('View on Screen', 'view_data', 'tryton-list'), 
            Button('Open PDF Tab', 'preview_tab', 'tryton-print', default=True), # <--- NEW BUTTON
        ])
    
    # State actions
    view_data = StateAction('custom_reports.act_view_report_data')
    preview_tab = StateAction('custom_reports.act_preview_url') # <--- POINTS TO URL ACTION

    def do_view_data(self, action):
        """ Dynamically filters the Tryton list view """
        action['pyson_domain'] = PYSONEncoder().encode([
            ('account', '=', self.start.account.id),
            ('date', '>=', self.start.start_date),
            ('date', '<=', self.start.end_date),
        ])
        action['name'] = f"{self.start.report_type.replace('_', ' ').title()} - {self.start.account.name}"
        return action, {}

    def do_preview_tab(self, action):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        
        data = {
            'account_id': self.start.account.id,
            'start_date': self.start.start_date,
            'end_date': self.start.end_date,
            'company_name': 'Rays Creation'
        }
        
        # 1. Get your raw HTML string
        if self.start.report_type == 'cash_book':
            html_content = CashBookReport.get_html([], data)
        else:
            html_content = GeneralLedgerReport.get_html([], data)
            
        # 2. CONVERT HTML TO PDF USING WEASYPRINT
        pdf_bytes = WeasyHTML(string=html_content).write_pdf()
        
        # 3. Save as a true PDF attachment
        filename = f"{self.start.report_type}_{self.start.account.code}.pdf"
        attachment = Attachment.create([{
            'name': filename,
            'type': 'data',
            'data': pdf_bytes,
            'resource': f"account.account,{self.start.account.id}",
        }])[0]
        
        # 4. Open the new tab pointing to our controller
        db_name = Transaction().database.name
        action['url'] = f"/{db_name}/custom_reports/preview/{attachment.id}"
        
        return action, {}