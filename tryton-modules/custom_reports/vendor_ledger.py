import os
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
        if hasattr(party_id, 'id'):
            party_id = party_id.id

        start_date = data.get('start_date')
        end_date = data.get('end_date')

        doc = tags.html()

        domain = []
        if start_date:
            domain.append(('date', '>=', start_date))
        if end_date:
            domain.append(('date', '<=', end_date))

        if party_id:
            domain.append(['OR', ('party', '=', party_id), ('custom_party', '=', party_id)])
        else:
            domain.append(['OR', ('party', '!=', None), ('custom_party', '!=', None)])

        lines = MoveLine.search(domain)

        def get_party(line):
            return line.party or getattr(line, 'custom_party', None)

        # Sort and group
        lines.sort(key=lambda l: (
            get_party(l).name if get_party(l) else '', 
            l.date.strftime('%Y%m%d') if l.date else '',
            l.move.id if l.move else 0,
            l.id
        ))
        grouped_lines = groupby(lines, key=get_party)

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
                    party_lines = list(party_lines)
                    if not party:
                        continue

                    # Calculate Opening Balance
                    opening_balance = Decimal('0.00')
                    if start_date:
                        opening_domain = [
                            ('date', '<', start_date),
                            ['OR', ('party', '=', party.id), ('custom_party', '=', party.id)]
                        ]
                        opening_lines = MoveLine.search(opening_domain)
                        for ol in opening_lines:
                            o_debit = ol.debit or Decimal('0.00')
                            o_credit = ol.credit or Decimal('0.00')
                            opening_balance += (o_debit - o_credit)

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
                            running_balance = opening_balance

                            if start_date:
                                with tags.tr(style="background-color: #f8fafc; font-weight: bold; color: #333;"):
                                    tags.td(start_date.strftime('%d-%b-%y'), cls="text-center")
                                    tags.td("-", cls="text-center")
                                    tags.td("-", cls="text-center")
                                    tags.td("-")
                                    tags.td("Opening Balance Brought Forward")
                                    tags.td("-", cls="text-right")
                                    tags.td("-", cls="text-right")
                                    tags.td(f"{running_balance:,.2f}", cls="text-right")

                            # Group lines by their Move
                            move_groups = groupby(party_lines, key=lambda l: l.move)

                            for move, m_lines_iter in move_groups:
                                m_lines = list(m_lines_iter)

                                if not move:
                                    for l in m_lines:
                                        debit = l.debit or Decimal('0.00')
                                        credit = l.credit or Decimal('0.00')
                                        running_balance += (debit - credit)
                                        with tags.tr():
                                            tags.td(l.date.strftime('%d-%b-%y') if l.date else '', cls="text-center")
                                            tags.td("-", cls="text-center")
                                            tags.td("-", cls="text-center")
                                            tags.td(l.account.name if l.account else '')
                                            tags.td(str(l.description or ''))
                                            tags.td(f"{debit:,.2f}" if debit else "-", cls="text-right")
                                            tags.td(f"{credit:,.2f}" if credit else "-", cls="text-right")
                                            tags.td(f"{running_balance:,.2f}", cls="text-right font-bold")
                                    continue

                                date_str = m_lines[0].date.strftime('%d-%b-%y') if m_lines[0].date else ''
                                voucher = str(move.number or '')
                                invoice_no = ''
                                if move.origin:
                                    invoice_no = getattr(move.origin, 'number', getattr(move.origin, 'rec_name', ''))

                                # Calculate Gross Value by ensuring BOTH party fields are empty on the opposite side
                                gross_val = sum(
                                    ((ml.debit or Decimal('0.00')) - (ml.credit or Decimal('0.00')))
                                    for ml in move.lines if not ml.party and not getattr(ml, 'custom_party', None)
                                )

                                # ========================================================
                                # SCENARIO A: Single Line Gross Invoice Value
                                # ========================================================
                                if gross_val > Decimal('0.00'):
                                    party_debit = sum(l.debit or Decimal('0.00') for l in m_lines)
                                    party_credit = sum(l.credit or Decimal('0.00') for l in m_lines)
                                    actual_net = party_debit - party_credit

                                    running_balance += actual_net

                                    with tags.tr():
                                        tags.td(date_str, cls="text-center")
                                        tags.td(voucher, cls="text-center")
                                        tags.td(invoice_no, cls="text-center")
                                        tags.td("Trade Payables")
                                        tags.td("Gross Invoice Value")
                                        tags.td("-", cls="text-right")
                                        tags.td(f"{gross_val:,.2f}", cls="text-right")
                                        tags.td(f"{running_balance:,.2f}", cls="text-right font-bold")

                                # ========================================================
                                # SCENARIO B: Split Lines for Payments, Advances & Expenses
                                # ========================================================
                                else:
                                    for l in m_lines:
                                        debit = l.debit or Decimal('0.00')
                                        credit = l.credit or Decimal('0.00')
                                        running_balance += (debit - credit)

                                        account_name = l.account.name if l.account else ''
                                        desc = str(l.description or (l.move.description if l.move else ''))
                                        if not desc:
                                            desc = ""

                                        with tags.tr():
                                            tags.td(date_str, cls="text-center")
                                            tags.td(voucher, cls="text-center")
                                            tags.td(invoice_no, cls="text-center")
                                            tags.td(account_name)
                                            tags.td(desc)
                                            tags.td(f"{debit:,.2f}" if debit else "-", cls="text-right")
                                            tags.td(f"{credit:,.2f}" if credit else "-", cls="text-right")
                                            tags.td(f"{running_balance:,.2f}", cls="text-right font-bold")

        return doc.render()