import os
from decimal import Decimal
from itertools import groupby
from datetime import date
import dominate.tags as tags
from trytond.pool import Pool
from trytond.modules.html_report.html_report import HTMLReport
from .utils import REPORT_CSS

class ExpenseReport(HTMLReport):
    __name__ = 'account.expense_report_custom'

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

        # 1. Extract parameters
        raw_start = data.get('start_date')
        raw_end = data.get('end_date')
        start_date_str = raw_start.strftime('%d-%b-%Y') if hasattr(raw_start, 'strftime') else str(raw_start or '')
        end_date_str = raw_end.strftime('%d-%b-%Y') if hasattr(raw_end, 'strftime') else str(raw_end or '')
        company_name = data.get('company_name', 'RAYS Creations')

        # 2. Filter accounts by codes starting with 6 or 7
        expense_accounts = Account.search([
            'OR',
            ('code', 'like', '5%'),
            ['OR',
                ('code', 'like', '6%'),
                ('code', 'like', '7%')
            ]
        ])
        expense_account_ids = [acc.id for acc in expense_accounts]

        # 3. Build Domain and Fetch Lines
        domain = [
            ('account', 'in', expense_account_ids),
        ]
        if raw_start:
            domain.append(('date', '>=', raw_start))
        if raw_end:
            domain.append(('date', '<=', raw_end))
            
        move_lines = MoveLine.search(domain)

        # 4. Sort and Group Data Expense-wise
        # Sort first by Account Name, then by Date so the groupby works perfectly
        sorted_lines = sorted(move_lines, key=lambda l: (
            l.account.name if l.account else '',
            l.date or date.min
        ))
        
        # Group the sorted lines by the account object
        grouped_expenses = groupby(sorted_lines, key=lambda l: l.account)

        # 5. Build HTML Report
        doc = tags.html()
        with doc:
            with tags.head():
                tags.style(REPORT_CSS)
                
            with tags.body():
                with tags.div(cls="report-header"):
                    tags.h1("Expense Report")
                    tags.h3(company_name)

                with tags.div(cls="meta-info"):
                    tags.div(f"Period: {start_date_str} to {end_date_str}", cls="font-bold")

                if not move_lines:
                    with tags.table():
                        with tags.thead():
                            with tags.tr():
                                tags.th("Notice", cls="text-center")
                        with tags.tbody():
                            with tags.tr():
                                tags.td("No expenses found for the selected criteria.", cls="text-center")
                else:
                    grand_total = Decimal('0.00')

                    # Loop through each expense account group
                    for account, lines in grouped_expenses:
                        acc_name = f"{account.name} ({account.code})" if account else "Unknown Account"
                        
                        # Sub-header for the specific Expense Account
                        tags.h3(acc_name, style="margin: 25px 0 8px 0; color: #0f172a; font-size: 14px; font-weight: bold; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;")
                        
                        with tags.table():
                            with tags.thead():
                                with tags.tr():
                                    tags.th("Date", cls="text-center", style="width: 90px;")
                                    tags.th("Invoice / Ref No", cls="text-center", style="width: 140px;")
                                    tags.th("Description")
                                    tags.th("Amount", cls="text-right", style="width: 120px;")
                            
                            with tags.tbody():
                                sub_total = Decimal('0.00')
                                
                                for line in lines:
                                    net_amount = (line.debit or Decimal('0.00')) - (line.credit or Decimal('0.00'))
                                    sub_total += net_amount
                                    grand_total += net_amount
                                    
                                    invoice_no = ''
                                    if line.move and line.move.origin:
                                        origin = line.move.origin
                                        invoice_no = getattr(origin, 'number', getattr(origin, 'rec_name', ''))

                                    with tags.tr():
                                        tags.td(line.date.strftime('%d-%b-%Y') if line.date else '', cls="text-center")
                                        tags.td(str(invoice_no), cls="text-center")
                                        tags.td(str(line.description or (line.move.description if line.move else '-')))
                                        tags.td(f"{net_amount:,.2f}", cls="text-right")

                                # Subtotal row for the current account
                                with tags.tr(cls="total-row", style="background-color: #f4f6f7; border-top: 2px solid #2c3e50;"):
                                    tags.td(f"TOTAL: {account.name.upper() if account else ''}", colspan="3", cls="text-right", style="padding: 8px; color: #7f8c8d; font-weight: bold;")
                                    tags.td(f"{sub_total:,.2f}", cls="text-right", style="padding: 8px; color: #2c3e50; font-weight: bold;")

                    # Grand Total block at the bottom of the report
                    with tags.div(style="margin-top: 30px; text-align: right; padding: 15px; background-color: #1e293b; color: #ffffff; border-radius: 4px; font-size: 14px; font-weight: bold;"):
                        tags.span("GRAND TOTAL EXPENSES: ", style="margin-right: 15px;")
                        tags.span(f"{grand_total:,.2f}")

        return doc.render()