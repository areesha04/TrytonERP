import os
from decimal import Decimal
from datetime import date
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
        Invoice = pool.get('account.invoice')
        InvoiceLine = pool.get('account.invoice.line')
        MoveLine = pool.get('account.move.line')
        Account = pool.get('account.account')

        # 1. Extract wizard parameters
        raw_start = data.get('start_date')
        raw_end = data.get('end_date')
        start_date_str = raw_start.strftime('%d-%b-%Y') if hasattr(raw_start, 'strftime') else str(raw_start or '')
        end_date_str = raw_end.strftime('%d-%b-%Y') if hasattr(raw_end, 'strftime') else str(raw_end or '')
        
        supplier_id = data.get('supplier_id') or data.get('party_id') or data.get('party')
        company_name = data.get('company_name', 'RAYS Creations')

        # 2. Identify the Deposit/Advance Account(s)
        advance_account_id = data.get('advance_account_id')
        if advance_account_id:
            adv_acc_ids = [advance_account_id]
        else:
            adv_accounts = Account.search(['OR', ('name', 'ilike', '%Advance%'), ('name', 'ilike', '%Deposit%')])
            adv_acc_ids = [a.id for a in adv_accounts]

        # ==========================================
        # CALCULATE OPENING BALANCES (Before start_date)
        # ==========================================
        opening_advances = {}
        if raw_start:
            op_inv_domain = [
                ('invoice.type', '=', 'in'),
                ('invoice.state', 'in', ['posted', 'paid']),
                ('account', 'in', adv_acc_ids if adv_acc_ids else [0]),
                ('invoice.invoice_date', '<', raw_start)
            ]
            if supplier_id: op_inv_domain.append(('invoice.party', '=', supplier_id))
            
            for il in InvoiceLine.search(op_inv_domain):
                party = il.invoice.party
                amount = Decimal(str(il.amount or '0.00'))
                opening_advances[party] = opening_advances.get(party, Decimal('0.00')) + amount

            op_move_domain = [
                ('move.state', '=', 'posted'),
                ('account', 'in', adv_acc_ids if adv_acc_ids else [0]),
                ('party', '!=', None),
                ('date', '<', raw_start)
            ]
            if supplier_id: op_move_domain.append(('party', '=', supplier_id))
            
            for ml in MoveLine.search(op_move_domain):
                origin = getattr(ml.move, 'origin', None)
                if origin and getattr(origin, '__name__', '') == 'account.invoice':
                    continue
                    
                party = ml.party
                adv_given = Decimal(str(ml.debit or '0.00'))
                adv_recalled = Decimal(str(ml.credit or '0.00'))
                net_adv = adv_given - adv_recalled
                opening_advances[party] = opening_advances.get(party, Decimal('0.00')) + net_adv

        # ==========================================
        # SOURCE 1: ADVANCES (Invoice Lines & Move Lines)
        # ==========================================
        unified_advances = []

        inv_domain = [
            ('invoice.type', '=', 'in'),
            ('invoice.state', 'in', ['posted', 'paid']),
            ('account', 'in', adv_acc_ids if adv_acc_ids else [0])
        ]
        if raw_start: inv_domain.append(('invoice.invoice_date', '>=', raw_start))
        if raw_end: inv_domain.append(('invoice.invoice_date', '<=', raw_end))
        if supplier_id: inv_domain.append(('invoice.party', '=', supplier_id))
            
        deposit_inv_lines = InvoiceLine.search(inv_domain)
        for il in deposit_inv_lines:
            amount = Decimal(str(il.amount or '0.00'))
            adv_given = amount if amount > 0 else Decimal('0.00')
            adv_recalled = abs(amount) if amount < 0 else Decimal('0.00')
            
            unified_advances.append({
                'party': il.invoice.party,
                'date': il.invoice.invoice_date,
                'ref': il.invoice.reference or il.invoice.number or il.invoice.rec_name,
                'desc': f"[Invoice] {il.description or 'Advance Payment'}",
                'given': adv_given,
                'recalled': adv_recalled,
            })

        move_domain = [
            ('move.state', '=', 'posted'),
            ('account', 'in', adv_acc_ids if adv_acc_ids else [0]),
            ('party', '!=', None)
        ]
        if raw_start: move_domain.append(('date', '>=', raw_start))
        if raw_end: move_domain.append(('date', '<=', raw_end))
        if supplier_id: move_domain.append(('party', '=', supplier_id))
            
        deposit_move_lines = MoveLine.search(move_domain)
        for ml in deposit_move_lines:
            origin = getattr(ml.move, 'origin', None)
            if origin and getattr(origin, '__name__', '') == 'account.invoice':
                continue
                
            adv_given = Decimal(str(ml.debit or '0.00'))
            adv_recalled = Decimal(str(ml.credit or '0.00'))
            
            unified_advances.append({
                'party': ml.party,
                'date': ml.date,
                'ref': ml.move.number or ml.move.reference or ml.move.description or '',
                'desc': f"[Journal] {ml.description or ml.move.description or 'Advance Entry'}",
                'given': adv_given,
                'recalled': adv_recalled,
            })

        # ==========================================
        # SOURCE 2: TRADE PAYABLES (Unpaid Bills Only)
        # ==========================================
        vendor_payables = []
        
        payables_domain = [
            ('type', '=', 'in'),
            ('state', '=', 'posted')
        ]
        if raw_start: payables_domain.append(('invoice_date', '>=', raw_start))
        if raw_end: payables_domain.append(('invoice_date', '<=', raw_end))
        if supplier_id: payables_domain.append(('party', '=', supplier_id))
            
        invoices = Invoice.search(payables_domain)
        for inv in invoices:
            balance_amt = Decimal(str(inv.amount_to_pay or '0.00'))
            if balance_amt <= 0:
                continue  # Skip fully paid invoices
                
            total_amt = Decimal(str(inv.total_amount or '0.00'))
            allocated_amt = total_amt - balance_amt
            
            vendor_payables.append({
                'party': inv.party,
                'date': inv.invoice_date,
                'ref': inv.reference or inv.number or '',
                'desc': inv.description or 'Vendor Bill',
                'total': total_amt,
                'allocated': allocated_amt,
                'balance': balance_amt
            })

        # ==========================================
        # GROUP BY VENDOR
        # ==========================================
        grouped_data = {}
        
        for party in opening_advances.keys():
            if party not in grouped_data:
                grouped_data[party] = {'advances': [], 'payables': []}
        
        for rec in unified_advances:
            party = rec['party']
            if party not in grouped_data:
                grouped_data[party] = {'advances': [], 'payables': []}
            grouped_data[party]['advances'].append(rec)
            
        for rec in vendor_payables:
            party = rec['party']
            if party not in grouped_data:
                grouped_data[party] = {'advances': [], 'payables': []}
            grouped_data[party]['payables'].append(rec)
            
        vendors = sorted(list(grouped_data.keys()), key=lambda p: p.name if p else '')

        for party in grouped_data:
            grouped_data[party]['advances'].sort(key=lambda r: r['date'] or date.min)
            grouped_data[party]['payables'].sort(key=lambda r: r['date'] or date.min)

        # ==========================================
        # BUILD HTML REPORT
        # ==========================================
        doc = tags.html()
        with doc:
            with tags.head():
                tags.style(REPORT_CSS)
                
            with tags.body():
                with tags.div(cls="report-header"):
                    tags.h1("Vendor Advance & Trade Payables")
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
                        tags.span("Configuration Warning: No account with 'Advance' or 'Deposit' in its name was found.")

                if not vendors:
                    with tags.table():
                        with tags.thead():
                            with tags.tr():
                                tags.th("Notice", cls="text-center")
                        with tags.tbody():
                            with tags.tr():
                                tags.td("No advance payments or trade payables found for the selected criteria.", cls="text-center")
                else:
                    for vendor in vendors:
                        v_data = grouped_data[vendor]
                        adv_lines = v_data['advances']
                        pay_lines = v_data['payables']
                        
                        op_balance = opening_advances.get(vendor, Decimal('0.00'))

                        # --- Vendor Title ---
                        tags.h2(vendor.name if vendor else "Unknown Supplier", style="margin: 35px 0 10px 0; color: #0f172a; font-size: 18px; font-weight: bold; border-bottom: 2px solid #3b82f6; padding-bottom: 5px;")

                        running_adv_balance = op_balance
                        total_payable_balance = Decimal('0.00')

                        # --- Section 1: Advances Ledger ---
                        if adv_lines or op_balance != 0:
                            tags.h3("1. Advance Payments & Allocations", style="font-size: 14px; margin-top: 15px; color: #475569;")
                            with tags.table(style="margin-bottom: 20px;"):
                                with tags.thead():
                                    with tags.tr():
                                        tags.th("Date", cls="text-center", style="width: 85px;")
                                        tags.th("Ref.")
                                        tags.th("Description")
                                        tags.th("Advance Paid (+)", cls="text-right", style="width: 110px;")
                                        tags.th("Recalled (-)", cls="text-right", style="width: 140px;")
                                        tags.th("Remaining Balance", cls="text-right", style="width: 120px;")
                                with tags.tbody():
                                    
                                    if raw_start:
                                        with tags.tr(style="background-color: #f1f5f9; font-style: italic; color: #64748b;"):
                                            tags.td(start_date_str, cls="text-center")
                                            tags.td("-")
                                            tags.td("Opening Balance (Prior Advances)")
                                            tags.td("-", cls="text-right")
                                            tags.td("-", cls="text-right")
                                            tags.td(f"{op_balance:,.2f}", cls="text-right", style="font-weight: bold;")

                                    total_given = Decimal('0.00')
                                    total_recalled = Decimal('0.00')
                                    
                                    for row in adv_lines:
                                        p_date = row['date'].strftime('%d-%b-%Y') if row['date'] else ''
                                        adv_given = row['given']
                                        adv_recalled = row['recalled']
                                        
                                        total_given += adv_given
                                        total_recalled += adv_recalled
                                        running_adv_balance += (adv_given - adv_recalled)

                                        with tags.tr():
                                            tags.td(p_date, cls="text-center")
                                            tags.td(str(row['ref']))
                                            tags.td(row['desc'])
                                            tags.td(f"{adv_given:,.2f}" if adv_given else "-", cls="text-right")
                                            tags.td(f"{adv_recalled:,.2f}" if adv_recalled else "-", cls="text-right", style="color: #c0392b;" if adv_recalled else "")
                                            tags.td(f"{running_adv_balance:,.2f}", cls="text-right", style="font-weight: bold;")
                                            
                                    with tags.tr(cls="total-row", style="background-color: #f8fafc; font-weight: bold; border-top: 2px solid #64748b;"):
                                        tags.td("PERIOD TOTALS", colspan="3", cls="text-right", style="padding: 8px; color: #475569;")
                                        tags.td(f"{total_given:,.2f}", cls="text-right", style="padding: 8px;")
                                        tags.td(f"{total_recalled:,.2f}", cls="text-right", style="padding: 8px; color: #c0392b;")
                                        tags.td(f"{running_adv_balance:,.2f}", cls="text-right", style="padding: 8px; color: #0f172a;")

                        # --- Section 2: Trade Payables ---
                        if pay_lines:
                            tags.h3("2. Trade Payables (Vendor Bills)", style="font-size: 14px; margin-top: 15px; color: #475569;")
                            with tags.table(style="margin-bottom: 20px;"):
                                with tags.thead():
                                    with tags.tr():
                                        tags.th("Date", cls="text-center", style="width: 85px;")
                                        tags.th("Ref.")
                                        tags.th("Description")
                                        tags.th("Total Bill Amount", cls="text-right", style="width: 120px;")
                                        tags.th("Paid", cls="text-right", style="width: 120px;")
                                        tags.th("Balance Due", cls="text-right", style="width: 120px;")
                                with tags.tbody():
                                    total_bill = Decimal('0.00')
                                    total_allocated = Decimal('0.00')
                                    
                                    for row in pay_lines:
                                        p_date = row['date'].strftime('%d-%b-%Y') if row['date'] else ''
                                        r_total = row['total']
                                        r_alloc = row['allocated']
                                        r_bal = row['balance']
                                        
                                        total_bill += r_total
                                        total_allocated += r_alloc
                                        total_payable_balance += r_bal

                                        with tags.tr():
                                            tags.td(p_date, cls="text-center")
                                            tags.td(str(row['ref']))
                                            tags.td(row['desc'])
                                            tags.td(f"{r_total:,.2f}", cls="text-right")
                                            tags.td(f"{r_alloc:,.2f}" if r_alloc else "-", cls="text-right", style="color: #16a34a;" if r_alloc else "")
                                            tags.td(f"{r_bal:,.2f}", cls="text-right", style="font-weight: bold; color: #b91c1c;" if r_bal > 0 else "")
                                            
                                    with tags.tr(cls="total-row", style="background-color: #f8fafc; font-weight: bold; border-top: 2px solid #64748b;"):
                                        tags.td("PAYABLES TOTALS", colspan="3", cls="text-right", style="padding: 8px; color: #475569;")
                                        tags.td(f"{total_bill:,.2f}", cls="text-right", style="padding: 8px;")
                                        tags.td(f"{total_allocated:,.2f}", cls="text-right", style="padding: 8px; color: #16a34a;")
                                        tags.td(f"{total_payable_balance:,.2f}", cls="text-right", style="padding: 8px; color: #b91c1c;")
                        
                        # --- Section 3: Vendor Net Summary ---
                        with tags.div(style="background-color: #f1f5f9; border: 1px solid #cbd5e1; padding: 15px; border-radius: 4px; margin-top: 10px; display: flex; justify-content: space-between;"):
                            with tags.div(style="flex: 1;"):
                                tags.div(f"Available Advance:", style="font-weight: bold; color: #475569; font-size: 13px;")
                                tags.div(f"{running_adv_balance:,.2f}", style="font-size: 16px; font-weight: bold; color: #0f172a; margin-top: 4px;")
                            with tags.div(style="flex: 1;"):
                                tags.div(f"Outstanding Payables:", style="font-weight: bold; color: #475569; font-size: 13px;")
                                tags.div(f"{total_payable_balance:,.2f}", style="font-size: 16px; font-weight: bold; color: #b91c1c; margin-top: 4px;")
                            with tags.div(style="flex: 1; text-align: right;"):
                                tags.div(f"Net Vendor Balance:", style="font-weight: bold; color: #475569; font-size: 13px;")
                                net_balance = total_payable_balance - running_adv_balance
                                if net_balance > 0:
                                    tags.div(f"Payable: {net_balance:,.2f}", style="font-size: 16px; font-weight: bold; color: #b91c1c; margin-top: 4px;")
                                elif net_balance < 0:
                                    tags.div(f"Advance Surplus: {abs(net_balance):,.2f}", style="font-size: 16px; font-weight: bold; color: #16a34a; margin-top: 4px;")
                                else:
                                    tags.div("Settled (0.00)", style="font-size: 16px; font-weight: bold; color: #475569; margin-top: 4px;")
                        
                        tags.br()

        return doc.render()