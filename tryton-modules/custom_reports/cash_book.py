from decimal import Decimal
import dominate.tags as tags
from trytond.pool import Pool
from trytond.modules.html_report.html_report import HTMLReport
from .utils import REPORT_CSS

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

        if not records and 'account_id' in data and data['account_id']:
            records = Account.browse([data['account_id']])

        start_date = data.get('start_date', '01-01-2024')
        end_date = data.get('end_date', '31-12-2024')
        company_name = data.get('company_name', 'RAYS Creations')
        opening_balance = data.get('opening_balance', Decimal('0.00'))

        doc = tags.html()
        with doc:
            with tags.head():
                tags.style(REPORT_CSS)
                # Force landscape for Cash Book to fit side-by-side cleanly
                tags.style("@page { size: A4 landscape; margin: 10mm; }") 
            with tags.body():
                with tags.div(cls="report-header"):
                    tags.h1("Cash Book")
                    tags.h3(company_name)

                with tags.div(cls="meta-info"):
                    tags.div(f"Period: {start_date} to {end_date}", cls="font-bold")
                    tags.div(f"Opening Balance: {opening_balance:,.2f}", cls="font-bold")

                for account in records:
                    domain = [('account', '=', account.id)]
                    if start_date:
                        domain.append(('date', '>=', start_date))
                    if end_date:
                        domain.append(('date', '<=', end_date))

                    move_lines = MoveLine.search(domain, order=[('date', 'ASC'), ('id', 'ASC')])
                    receipts = [l for l in move_lines if l.debit and l.debit > 0]
                    payments = [l for l in move_lines if l.credit and l.credit > 0]

                    with tags.div(cls="cb-container"):
                        # RECEIPTS (Left Side)
                        with tags.div(cls="cb-side"):
                            tags.div("RECEIPTS (INFLOW)", cls="cb-title")
                            with tags.table(style="margin-bottom: 0;"):
                                with tags.thead():
                                    with tags.tr():
                                        tags.th("Date", cls="text-center", style="width: 60px;")
                                        tags.th("COA")
                                        tags.th("V#", cls="text-center", style="width: 60px;")
                                        tags.th("Description")
                                        tags.th("Amount", cls="text-right", style="width: 70px;")
                                with tags.tbody():
                                    for rec in receipts:
                                        co_name = ""
                                        if rec.move and rec.move.lines:
                                            for s_line in rec.move.lines:
                                                if s_line.account.id != account.id:
                                                    co_name = s_line.account.name
                                                    break
                                        if not co_name and rec.party:
                                            co_name = rec.party.name

                                        with tags.tr():
                                            tags.td(rec.date.strftime('%d-%b-%y') if rec.date else '', cls="text-center")
                                            tags.td(co_name)
                                            tags.td(str(rec.move.number or '') if rec.move else '', cls="text-center")
                                            tags.td(str(rec.description or (rec.move.description if rec.move else '')))
                                            tags.td(f"{rec.debit:,.2f}", cls="text-right")

                        # PAYMENTS (Right Side)
                        with tags.div(cls="cb-side"):
                            tags.div("PAYMENTS (OUTFLOW)", cls="cb-title")
                            with tags.table(style="margin-bottom: 0;"):
                                with tags.thead():
                                    with tags.tr():
                                        tags.th("Date", cls="text-center", style="width: 60px;")
                                        tags.th("COA")
                                        tags.th("V#", cls="text-center", style="width: 60px;")
                                        tags.th("Description")
                                        tags.th("Amount", cls="text-right", style="width: 70px;")
                                with tags.tbody():
                                    for pay in payments:
                                        co_names = []
                                        if pay.move and pay.move.lines:
                                            for s_line in pay.move.lines:
                                                # 1. Skip the main cash book account itself
                                                if s_line.account.id == account.id:
                                                    continue
                                                
                                                # 2. Skip any account that has the "Fund Transfer Bank/Cash" checkbox ticked
                                                if getattr(s_line.account, 'is_quick_entry_bank', False):
                                                    continue
                                                
                                                # Optional: If Sir Adeel's account does NOT have the checkbox ticked, 
                                                # but you still need to exclude it, keep this specific check:
                                                if 'adeel' in s_line.account.name.lower():
                                                    continue
                                                
                                                # 3. Append to list if not already there (prevents duplicates)
                                                if s_line.account.name not in co_names:
                                                    co_names.append(s_line.account.name)
                                        
                                        # 4. Join all valid offsetting accounts with a comma
                                        co_name = ", ".join(co_names)

                                        # Fallback to party name if the filters stripped out everything
                                        if not co_name and pay.party:
                                            co_name = pay.party.name

                                        with tags.tr():
                                            tags.td(pay.date.strftime('%d-%b-%y') if pay.date else '', cls="text-center")
                                            tags.td(co_name)
                                            tags.td(str(pay.move.number or '') if pay.move else '', cls="text-center")
                                            tags.td(str(pay.description or (pay.move.description if pay.move else '')))
                                            tags.td(f"{pay.credit:,.2f}", cls="text-right")

        return doc.render()