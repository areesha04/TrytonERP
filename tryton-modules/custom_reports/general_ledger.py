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
        # Helper function to aggressively hunt down the business partner name
        # checking standard 'party', as well as 'custom_party' and 'record_party'
        def get_party_name(rec):
            if not rec:
                return ''
            for field in ['party', 'custom_party', 'record_party']:
                if hasattr(rec, field) and getattr(rec, field):
                    val = getattr(rec, field)
                    return val.name if hasattr(val, 'name') else str(val)
            return ''

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
                    # Calculate opening balance before start_date
                    opening_lines = MoveLine.search([
                        ('account', '=', account.id),
                        ('date', '<', start_date)
                    ])
                    opening_balance = sum(
                        (line.debit or Decimal('0.00')) - (line.credit or Decimal('0.00'))
                        for line in opening_lines
                    )
                    running_balance = opening_balance

                    total_debit = Decimal('0.00')
                    total_credit = Decimal('0.00')

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
                                tags.th("Party")
                                tags.th("Description")
                                tags.th("Debit", cls="text-right", style="width: 80px;")
                                tags.th("Credit", cls="text-right", style="width: 80px;")
                                tags.th("Balance", cls="text-right", style="width: 90px;")

                        with tags.tbody():
                            # Opening Balance Row
                            with tags.tr():
                                tags.td("-", cls="text-center")
                                tags.td("-", cls="text-center")
                                tags.td("-", cls="text-center")
                                tags.td("Opening Balance", cls="font-bold")
                                tags.td("-")
                                tags.td("-", cls="text-right")
                                tags.td("-", cls="text-right")
                                tags.td(f"{running_balance:,.2f}", cls="text-right font-bold")

                            move_lines = MoveLine.search([
                                ('account', '=', account.id),
                                ('date', '>=', start_date),
                                ('date', '<=', end_date)
                            ], order=[('date', 'ASC'), ('id', 'ASC')])

                            for line in move_lines:
                                # Check for counterpart lines to expand multi-line entries
                                other_lines = [ml for ml in getattr(line.move, 'lines', []) if ml.id != line.id]

                                if other_lines:
                                    for sub_line in other_lines:
                                        sub_debit = Decimal('0.00')
                                        sub_credit = Decimal('0.00')

                                        # Map debit/credit relative to the main account line direction
                                        if (line.credit or Decimal('0.00')) > 0:
                                            sub_credit = sub_line.debit or Decimal('0.00')
                                            sub_debit = sub_line.credit or Decimal('0.00')
                                        else:
                                            sub_debit = sub_line.credit or Decimal('0.00')
                                            sub_credit = sub_line.debit or Decimal('0.00')

                                        if sub_debit == 0 and sub_credit == 0:
                                            continue

                                        running_balance += (sub_debit - sub_credit)
                                        total_debit += sub_debit
                                        total_credit += sub_credit

                                        # Extensive Partner Resolution Logic
                                        partner_name = get_party_name(sub_line)
                                        if not partner_name:
                                            partner_name = get_party_name(line)
                                        if not partner_name and line.move:
                                            partner_name = get_party_name(line.move)
                                            if not partner_name:
                                                for ml in getattr(line.move, 'lines', []):
                                                    partner_name = get_party_name(ml)
                                                    if partner_name: break
                                            if not partner_name and line.move.origin:
                                                partner_name = get_party_name(line.move.origin)

                                        acc_name = sub_line.account.name if sub_line.account else ''
                                        line_desc = sub_line.description or acc_name or line.description or (line.move.description if line.move else '')

                                        invoice_no = ''
                                        if line.move and line.move.origin:
                                            origin = line.move.origin
                                            invoice_no = getattr(origin, 'number', getattr(origin, 'rec_name', ''))

                                        with tags.tr():
                                            tags.td(line.date.strftime('%d-%b-%Y') if line.date else '', cls="text-center")
                                            tags.td(str(line.move.number or '') if line.move else '', cls="text-center")                                    
                                            tags.td(str(invoice_no), cls="text-center")
                                            tags.td(partner_name)
                                            tags.td(str(line_desc))
                                            tags.td(f"{sub_debit:,.2f}" if sub_debit else "-", cls="text-right")
                                            tags.td(f"{sub_credit:,.2f}" if sub_credit else "-", cls="text-right")
                                            tags.td(f"{running_balance:,.2f}", cls="text-right font-bold")
                                else:
                                    # Fallback for standard single-line entries
                                    debit = line.debit or Decimal('0.00')
                                    credit = line.credit or Decimal('0.00')
                                    running_balance += (debit - credit)

                                    total_debit += debit
                                    total_credit += credit

                                    # Extensive Partner Resolution Logic
                                    partner_name = get_party_name(line)
                                    if not partner_name and line.move:
                                        partner_name = get_party_name(line.move)
                                        if not partner_name:
                                            for ml in getattr(line.move, 'lines', []):
                                                partner_name = get_party_name(ml)
                                                if partner_name: break
                                        if not partner_name and line.move.origin:
                                            partner_name = get_party_name(line.move.origin)

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

                            # Total Row rendered once at the very end of the tbody content
                            with tags.tr(cls="font-bold"):
                                tags.td("Total", colspan="5", cls="text-right")
                                tags.td(f"{total_debit:,.2f}", cls="text-right")
                                tags.td(f"{total_credit:,.2f}", cls="text-right")
                                tags.td(f"{running_balance:,.2f}", cls="text-right")

        return doc.render()