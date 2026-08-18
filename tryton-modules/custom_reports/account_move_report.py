from trytond.pool import Pool
from trytond.modules.html_report.html_report import HTMLReport
from trytond.wizard import Wizard, StateAction
from trytond.transaction import Transaction
import dominate.tags as tags
from weasyprint import HTML as WeasyHTML
from decimal import Decimal

# ==========================================
# 1. UNIFIED HTML REPORT (Dynamic Title)
# ==========================================
class AccountMoveCustomReport(HTMLReport):
    __name__ = 'account.move.custom_report'

    @classmethod
    def get_html(cls, records, data):
        report_title = data.get('report_title', 'JOURNAL ENTRY')
        
        doc = tags.div(style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 12px; color: #333; padding: 20px 30px; position: relative; z-index: 1; max-width: 800px; margin: auto;")
        
        with doc:
            for move in records:
                with tags.table(style="width: 100%; margin-bottom: 25px; border-collapse: collapse;"):
                    with tags.tr():
                        with tags.td(style="width: 50%; vertical-align: bottom;"):
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
                            party_str = line.party.name if line.party else ""
                            
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

# ==========================================
# 2. SMART WIZARD CONTROLLER 
# ==========================================
class PreviewUniversalMoveWizard(Wizard):
    'Invisible Wizard for Direct PDF Download across multiple menus'
    __name__ = 'account.move.preview_universal_wizard'

    start_state = 'generate'
    generate = StateAction('custom_reports.act_preview_url') 

    # Fallback to satisfy Tryton's error dispatcher on Wizard objects
    @classmethod
    def raise_user_error(cls, *args, **kwargs):
        Pool().get('ir.model').raise_user_error(*args, **kwargs)

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
                # Route the warning through standard model to force the yellow window properly
                pool.get('ir.model').raise_user_warning(
                    f'draft_preview_qe_{record.id}', 
                    "Cannot print preview! No Account Move has been generated yet. Please post the entry first."
                )
                return action, {} # Required: safely closes wizard if user clicks "OK" to bypass warning
                
        elif active_model == 'custom.account.multi_expense':
            move = record.move
            report_title = "BANK/CASH PAYMENT"
            if not move:
                # Route the warning through standard model to force the yellow window properly
                pool.get('ir.model').raise_user_warning(
                    f'draft_preview_me_{record.id}', 
                    "Cannot print preview! No Account Move has been generated yet. Please post the entry first."
                )
                return action, {} # Required: safely closes wizard if user clicks "OK" to bypass warning
                
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
        
        # 4. Open in new tab
        db_name = Transaction().database.name
        action['url'] = f"/{db_name}/custom_reports/preview/{attachment.id}"
        
        return action, {}