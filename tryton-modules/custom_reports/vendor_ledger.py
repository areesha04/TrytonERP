from decimal import Decimal
import dominate.tags as tags
from itertools import groupby
from trytond.pool import Pool
from trytond.modules.html_report.html_report import HTMLReport
from .utils import REPORT_CSS

class VendorLedgerReport(HTMLReport):
    __name__ = 'account.vendor_ledger_custom'

    @classmethod
    def render(cls, action, report_context, lang=None):
        records = report_context.get('records', [])
        data = report_context.get('data', {})
        return cls.get_html(records, data)

    @classmethod
    def get_html(cls, records, data):
        pool = Pool()
        MoveLine = pool.get('account.move.line')

        party_id = data.get('party_id')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        doc = tags.html()
        
        domain = [('party', '!=', None)]
        if start_date:
            domain.append(('date', '>=', start_date))
        if end_date:
            domain.append(('date', '<=', end_date))
        if party_id:
            domain.append(('party', '=', party_id))
            
        lines = MoveLine.search(domain)
        lines.sort(key=lambda l: (l.party.name if l.party else '', l.date.strftime('%Y%m%d') if l.date else ''))
        grouped_lines = groupby(lines, key=lambda l: l.party)

        with doc:
            with tags.head():
                tags.style(REPORT_CSS)
            with tags.body():
                with tags.div(cls="report-header"):
                    tags.h1("Vendor Ledger")
                    tags.h3("Payables & Transactions")

                with tags.div(cls="meta-info"):
                    tags.div(f"Period: {start_date or '-'} to {end_date or '-'}", cls="font-bold")

                for party, party_lines in grouped_lines:
                    if not party:
                        continue

                    # Clean separation for each vendor
                    tags.h3(party.name, style="margin: 20px 0 10px 0; color: #0f172a;")
                    
                    with tags.table():
                        with tags.thead():
                            with tags.tr():
                                tags.th("Date", cls="text-center", style="width: 70px;")
                                tags.th("Voucher", cls="text-center", style="width: 80px;")
                                tags.th("Invoice", cls="text-center", style="width: 90px;")
                                tags.th("Account", style="width: 120px;")
                                tags.th("Description")
                                tags.th("Debit (In)", cls="text-right", style="width: 80px;")
                                tags.th("Credit (Out)", cls="text-right", style="width: 80px;")
                                tags.th("Balance", cls="text-right", style="width: 90px;")

                        with tags.tbody():
                            running_balance = Decimal('0.00')
                            for l in party_lines:
                                debit = l.debit or Decimal('0.00')
                                credit = l.credit or Decimal('0.00')
                                running_balance += (debit - credit)
                                
                                invoice_no = ''
                                if l.move and l.move.origin:
                                    origin = l.move.origin
                                    invoice_no = getattr(origin, 'number', getattr(origin, 'rec_name', ''))
                                    
                                with tags.tr():
                                    tags.td(l.date.strftime('%d-%b-%y') if l.date else '', cls="text-center")
                                    tags.td(str(l.move.number or '') if l.move else '', cls="text-center")
                                    tags.td(str(invoice_no), cls="text-center")
                                    tags.td(l.account.name if l.account else '')
                                    tags.td(str(l.description or (l.move.description if l.move else '')))
                                    tags.td(f"{debit:,.2f}" if debit else "-", cls="text-right")
                                    tags.td(f"{credit:,.2f}" if credit else "-", cls="text-right")
                                    tags.td(f"{running_balance:,.2f}", cls="text-right font-bold")

        return doc.render()