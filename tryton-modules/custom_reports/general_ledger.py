from decimal import Decimal
import dominate.tags as tags
from trytond.pool import Pool
from trytond.modules.html_report.html_report import HTMLReport
from .utils import REPORT_CSS

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

        if not records and 'account_id' in data and data['account_id']:
            records = Account.browse([data['account_id']])
            
        start_date = data.get('start_date', '01-01-2024')
        end_date = data.get('end_date', '31-12-2024')
        company_name = data.get('company_name', 'RAYS Creations')

        doc = tags.html()
        with doc:
            with tags.head():
                tags.style(REPORT_CSS)
            with tags.body():
                with tags.div(cls="report-header"):
                    tags.h1("General Ledger")
                    tags.h3(company_name)

                for account in records:
                    start_balance = Decimal('0.00')
                    running_balance = start_balance

                    # Account Meta Info
                    with tags.div(cls="meta-info"):
                        with tags.div():
                            tags.span("Account: ", cls="font-bold")
                            tags.span(f"{account.name} ({account.code})")
                        with tags.div(cls="text-right"):
                            tags.span(f"Period: {start_date} to {end_date}", cls="font-bold")

                    with tags.table():
                        with tags.thead():
                            with tags.tr():
                                tags.th("Date", cls="text-center", style="width: 70px;")
                                tags.th("Voucher", cls="text-center", style="width: 80px;")
                                tags.th("Invoice", cls="text-center", style="width: 90px;")
                                tags.th("Business Partner")
                                tags.th("Description")
                                tags.th("Debit", cls="text-right", style="width: 80px;")
                                tags.th("Credit", cls="text-right", style="width: 80px;")
                                tags.th("Balance", cls="text-right", style="width: 90px;")

                        with tags.tbody():
                            move_lines = MoveLine.search([
                                ('account', '=', account.id),
                                ('date', '>=', start_date),
                                ('date', '<=', end_date)
                            ], order=[('date', 'ASC'), ('id', 'ASC')])

                            for line in move_lines:
                                debit = line.debit or Decimal('0.00')
                                credit = line.credit or Decimal('0.00')
                                running_balance += (debit - credit)

                                # Business Partner Logic
                                partner_name = ''
                                if line.party and line.party.name:
                                    partner_name = line.party.name
                                elif line.move and line.move.origin and hasattr(line.move.origin, 'party') and line.move.origin.party:
                                    partner_name = line.move.origin.party.name

                                invoice_no = ''
                                if line.move and line.move.origin:
                                    origin = line.move.origin
                                    invoice_no = getattr(origin, 'number', getattr(origin, 'rec_name', ''))

                                with tags.tr():
                                    tags.td(line.date.strftime('%d-%b-%Y') if line.date else '', cls="text-center")
                                    tags.td(str(line.move.number or '') if line.move else '', cls="text-center")                                    
                                    tags.td(str(invoice_no), cls="text-center")
                                    tags.td(partner_name)
                                    tags.td(str(line.description or (line.move.description if line.move else '')))
                                    tags.td(f"{debit:,.2f}" if debit else "-", cls="text-right")
                                    tags.td(f"{credit:,.2f}" if credit else "-", cls="text-right")
                                    tags.td(f"{running_balance:,.2f}", cls="text-right font-bold")

        return doc.render()