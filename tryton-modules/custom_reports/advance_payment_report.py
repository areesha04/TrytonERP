import os
from decimal import Decimal
import dominate.tags as tags
from trytond.pool import Pool
from trytond.modules.html_report.html_report import HTMLReport
from .utils import REPORT_CSS

class VendorAdvanceDepositReport(HTMLReport):
    __name__ = 'custom.vendor.advance.report'

    @classmethod
    def render(cls, action, report_context, lang=None):
        records = report_context.get('records', [])
        data = report_context.get('data', {})
        return cls.get_html(records, data)

    @classmethod
    def get_html(cls, records, data):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Account = pool.get('account.account')

        # 1. Extract wizard parameters
        raw_start = data.get('start_date')
        raw_end = data.get('end_date')
        start_date_str = raw_start.strftime('%d-%b-%Y') if hasattr(raw_start, 'strftime') else str(raw_start or '')
        end_date_str = raw_end.strftime('%d-%b-%Y') if hasattr(raw_end, 'strftime') else str(raw_end or '')
        
        supplier_id = data.get('supplier_id')
        company_name = data.get('company_name', 'RAYS Creations')

        # 2. Identify the Deposit/Advance Account(s)
        advance_account_id = data.get('advance_account_id')
        if advance_account_id:
            adv_acc_ids = [advance_account_id]
        else:
            # Dynamically fetch accounts designated for deposits/advances
            adv_accounts = Account.search(['OR', ('name', 'ilike', '%Advance%'), ('name', 'ilike', '%Deposit%')])
            adv_acc_ids = [a.id for a in adv_accounts]

        # 3. Fetch specific invoice lines hitting the advance accounts
        line_domain = [
            ('invoice.type', '=', 'in'),
            ('invoice.state', 'in', ['posted', 'paid']),
            ('account', 'in', adv_acc_ids if adv_acc_ids else [0])
        ]
        
        if raw_start:
            line_domain.append(('invoice.invoice_date', '>=', raw_start))
        if raw_end:
            line_domain.append(('invoice.invoice_date', '<=', raw_end))
        if supplier_id:
            line_domain.append(('invoice.party', '=', supplier_id))
            
        deposit_lines = InvoiceLine.search(line_domain, order=[('invoice.party', 'ASC'), ('invoice.invoice_date', 'ASC'), ('id', 'ASC')])

        # 4. Group data by Supplier
        grouped_lines = {}
        for line in deposit_lines:
            party = line.invoice.party
            if party not in grouped_lines:
                grouped_lines[party] = []
            grouped_lines[party].append(line)
            
        vendors = sorted(list(grouped_lines.keys()), key=lambda p: p.name if p else '')

        # 5. Build HTML Report
        doc = tags.html()
        with doc:
            with tags.head():
                tags.style(REPORT_CSS)
                
            with tags.body():
                with tags.div(cls="report-header"):
                    tags.h1("Supplier Advance Payments Ledger")
                    tags.h3(company_name)
                    
                    with tags.div(cls="header-line"):
                        tags.div(cls="line-dark")
                        tags.div(cls="line-red")

                with tags.div(cls="meta-info"):
                    tags.div(f"Period: {start_date_str} to {end_date_str}", cls="font-bold")
                    if supplier_id and vendors:
                        tags.div(f"Supplier: {vendors[0].name}", cls="font-bold")
                    elif not supplier_id:
                        tags.div("Supplier: All Suppliers", cls="font-bold")

                if not adv_acc_ids:
                    with tags.div(style="background-color: #fee2e2; color: #991b1b; padding: 10px; border: 1px solid #f87171; text-align: center; margin-bottom: 20px; font-weight: bold;"):
                        tags.span("Configuration Warning: No account with 'Advance' or 'Deposit' in its name was found. Ensure your chart of accounts is configured properly.")

                if not vendors:
                    with tags.table():
                        with tags.thead():
                            with tags.tr():
                                tags.th("Notice", cls="text-center")
                        with tags.tbody():
                            with tags.tr():
                                tags.td("No advance payments found for the selected criteria.", cls="text-center")
                else:
                    for vendor in vendors:
                        v_lines = grouped_lines[vendor]

                        # Supplier Header
                        tags.h3(vendor.name if vendor else "Unknown Supplier", style="margin: 25px 0 8px 0; color: #0f172a; font-size: 14px; font-weight: bold; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px;")

                        with tags.table():
                            with tags.thead():
                                with tags.tr():
                                    tags.th("Date", cls="text-center", style="width: 85px;")
                                    tags.th("Invoice Ref.")
                                    tags.th("Description")
                                    tags.th("Advance Paid (+)", cls="text-right", style="width: 110px;")
                                    tags.th("Advance Recalled (-)", cls="text-right", style="width: 120px;")
                                    tags.th("Remaining Balance", cls="text-right", style="width: 120px;")
                            with tags.tbody():
                                total_given = Decimal('0.00')
                                total_recalled = Decimal('0.00')
                                running_balance = Decimal('0.00')
                                
                                for line in v_lines:
                                    p_date = line.invoice.invoice_date.strftime('%d-%b-%Y') if line.invoice and line.invoice.invoice_date else ''
                                    inv_ref = line.invoice.reference or line.invoice.number or line.invoice.rec_name
                                    
                                    amount = Decimal(str(line.amount or '0.00'))
                                    
                                    adv_given = Decimal('0.00')
                                    adv_recalled = Decimal('0.00')
                                    
                                    # Positive amount = Advance Created
                                    # Negative amount = Advance Recalled/Allocated
                                    if amount > 0:
                                        adv_given = amount
                                        action_desc = line.description or "Advance Payment Issued"
                                    else:
                                        adv_recalled = abs(amount)
                                        action_desc = line.description or "Advance Recalled"
                                        
                                    total_given += adv_given
                                    total_recalled += adv_recalled
                                    running_balance += (adv_given - adv_recalled)

                                    with tags.tr():
                                        tags.td(p_date, cls="text-center")
                                        tags.td(str(inv_ref))
                                        tags.td(action_desc)
                                        tags.td(f"{adv_given:,.2f}" if adv_given else "-", cls="text-right")
                                        tags.td(f"{adv_recalled:,.2f}" if adv_recalled else "-", cls="text-right", style="color: #c0392b;" if adv_recalled else "")
                                        tags.td(f"{running_balance:,.2f}", cls="text-right", style="font-weight: bold;")
                                        
                                # Supplier Totals Footer
                                with tags.tr(cls="total-row", style="background-color: #f4f6f7; font-weight: bold; border-top: 2px solid #2c3e50;"):
                                    tags.td(f"TOTAL FOR {vendor.name.upper() if vendor else 'UNKNOWN'}", colspan="3", cls="text-right", style="padding: 10px; color: #7f8c8d;")
                                    tags.td(f"{total_given:,.2f}", cls="text-right", style="padding: 10px; color: #2c3e50;")
                                    tags.td(f"{total_recalled:,.2f}", cls="text-right", style="padding: 10px; color: #c0392b;")
                                    tags.td(f"{running_balance:,.2f}", cls="text-right", style="padding: 10px; color: #2c3e50; font-size: 13px;")

        return doc.render()