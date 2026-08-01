from decimal import Decimal
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

        start_date = data.get('start_date', '01-01-2024')
        end_date = data.get('end_date', '31-12-2024')
        company_name = data.get('company_name', 'Rays Creation')

        expense_accounts = Account.search([('type.expense', '=', True)])
        expense_account_ids = [acc.id for acc in expense_accounts]

        domain = [
            ('account', 'in', expense_account_ids),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ]
        move_lines = MoveLine.search(domain, order=[('date', 'ASC'), ('id', 'ASC')])

        doc = tags.html()
        with doc:
            with tags.head():
                tags.style(REPORT_CSS)
            with tags.body():
                with tags.div(cls="report-header"):
                    tags.h1("Expense Report")
                    tags.h3(company_name)

                with tags.div(cls="meta-info"):
                    tags.div(f"Period: {start_date} to {end_date}", cls="font-bold")

                with tags.table():
                    with tags.thead():
                        with tags.tr():
                            tags.th("Date", cls="text-center", style="width: 80px;")
                            tags.th("Account (COA)")
                            tags.th("Invoice No", cls="text-center", style="width: 110px;")
                            tags.th("Description")
                            tags.th("Amount", cls="text-right", style="width: 100px;")

                    with tags.tbody():
                        total_expense = Decimal('0.00')
                        for line in move_lines:
                            net_amount = (line.debit or Decimal('0.00')) - (line.credit or Decimal('0.00'))
                            total_expense += net_amount
                            
                            invoice_no = ''
                            if line.move and line.move.origin:
                                origin = line.move.origin
                                invoice_no = getattr(origin, 'number', getattr(origin, 'rec_name', ''))

                            with tags.tr():
                                tags.td(line.date.strftime('%d-%b-%Y') if line.date else '', cls="text-center")
                                tags.td(f"{line.account.name} ({line.account.code})" if line.account else '')
                                tags.td(str(invoice_no), cls="text-center")
                                tags.td(str(line.description or (line.move.description if line.move else '')))
                                tags.td(f"{net_amount:,.2f}", cls="text-right")

                        with tags.tr(cls="total-row"):
                            tags.td("Total Expenses", colspan="4", cls="text-right")
                            tags.td(f"{total_expense:,.2f}", cls="text-right")

        return doc.render()