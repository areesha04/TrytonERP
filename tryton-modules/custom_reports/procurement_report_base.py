import os
from decimal import Decimal
from itertools import groupby
import dominate.tags as tags
from trytond.pool import Pool
from trytond.modules.html_report.html_report import HTMLReport

class ProcurementCustomReport(HTMLReport):
    __name__ = 'custom.procurement.report'

    @classmethod
    def render(cls, action, report_context, lang=None):
        records = report_context.get('records', [])
        data = report_context.get('data', {})
        return cls.get_html(records, data)

    @classmethod
    def get_html(cls, records, data):
        pool = Pool()
        PurchaseLine = pool.get('purchase.line')

        # 1. Dynamically read the CSS file
        css_path = os.path.join(os.path.dirname(__file__), 'procurement.css')
        with open(css_path, 'r') as css_file:
            procurement_css = css_file.read()

        # 2. Extract and format parameters from wizard data
        raw_start = data.get('start_date')
        raw_end = data.get('end_date')
        start_date_str = raw_start.strftime('%d-%b-%Y') if hasattr(raw_start, 'strftime') else str(raw_start or '')
        end_date_str = raw_end.strftime('%d-%b-%Y') if hasattr(raw_end, 'strftime') else str(raw_end or '')
        
        report_type = data.get('report_type', 'purchase_register')
        company_name = data.get('company_name', 'RAYS Creations')

        # ---------------------------------------------------------
        # ENFORCE FILTER RULES (Ignore hidden wizard values)
        # ---------------------------------------------------------
        if report_type in ['purchase_register', 'rate_history']:
            supplier_id = None
            product_id = data.get('product_id')
        else:
            supplier_id = data.get('supplier_id')
            product_id = None

        # Map technical keys to complete, professional report titles
        report_titles = {
            'purchase_register': 'Purchase Register',
            'supplier_wise': 'Supplier-wise Purchase Report',
            'rate_history': 'Purchase Rate History Report',
            'grn_report': 'Goods Receiving Note (GRN) Report',
            'purchase_invoice': 'Purchase Invoice Report',
        }
        title = report_titles.get(report_type, report_type.replace('_', ' ').title())

        # 3. Build Tryton ORM Domain dynamically
        domain = []
        if raw_start:
            domain.append(('purchase.purchase_date', '>=', raw_start))
        if raw_end:
            domain.append(('purchase.purchase_date', '<=', raw_end))
        if supplier_id:
            domain.append(('purchase.party', '=', supplier_id))
        if product_id:
            domain.append(('product', '=', product_id))

        purchase_lines = PurchaseLine.search(domain, order=[('purchase.purchase_date', 'ASC')])

        # Resolve supplier name for header
        specific_supplier_name = ''
        if supplier_id and purchase_lines:
            for l in purchase_lines:
                if l.purchase and l.purchase.party:
                    specific_supplier_name = l.purchase.party.name
                    break

        # Resolve product name for header
        specific_product_name = ''
        if product_id and purchase_lines:
            for l in purchase_lines:
                if l.product:
                    specific_product_name = f"[{l.product.code}] {l.product.name}" if l.product.code else l.product.name
                    break

        doc = tags.html()
        with doc:
            with tags.head():
                tags.style(procurement_css)
                
            with tags.body():
                with tags.div(cls="report-header"):
                    tags.h1(title)
                    tags.h3(company_name)
                    
                    with tags.div(cls="header-line"):
                        tags.div(cls="line-dark")
                        tags.div(cls="line-red")

                with tags.div(cls="meta-info"):
                    tags.div(f"Period: {start_date_str} to {end_date_str}", cls="font-bold")
                    
                    # Display the active filter cleanly in the top right
                    if specific_supplier_name:
                        tags.div(f"Supplier: {specific_supplier_name}", cls="font-bold")
                    elif specific_product_name:
                        tags.div(f"Product: {specific_product_name}", cls="font-bold")

                if not purchase_lines:
                    with tags.table():
                        with tags.thead():
                            with tags.tr():
                                tags.th("Notice", cls="text-center")
                        with tags.tbody():
                            with tags.tr():
                                tags.td("No records found for the selected criteria.", cls="text-center")
                else:
                    # ==========================================
                    # 1. PURCHASE REGISTER
                    # ==========================================
                    if report_type == 'purchase_register':
                        with tags.table():
                            with tags.thead():
                                with tags.tr():
                                    tags.th("Purchase Date", cls="text-center", style="width: 80px;")
                                    tags.th("Purchase Order No.", cls="text-center")
                                    # Conditionally hide Product columns
                                    if not specific_product_name:
                                        tags.th("Product Code")
                                        tags.th("Product Name")
                                    tags.th("Quantity", cls="text-right", style="width: 70px;")
                                    tags.th("Unit Rate", cls="text-right", style="width: 80px;")
                                    tags.th("Total Amount", cls="text-right", style="width: 90px;")
                            with tags.tbody():
                                total_qty = Decimal('0.00')
                                total_amount = Decimal('0.00')
                                for line in purchase_lines:
                                    p_date = line.purchase.purchase_date.strftime('%d-%b-%Y') if line.purchase and line.purchase.purchase_date else ''
                                    po_no = line.purchase.number or line.purchase.rec_name if line.purchase else ''
                                    prod_code = line.product.code if line.product else ''
                                    prod_name = line.product.name if line.product else (line.description or '')
                                    qty = Decimal(str(line.quantity or '0.0'))
                                    unit_price = Decimal(str(line.unit_price or '0.0'))
                                    amount = Decimal(str(line.amount or (qty * unit_price)))

                                    total_qty += qty
                                    total_amount += amount

                                    with tags.tr():
                                        tags.td(p_date, cls="text-center")
                                        tags.td(str(po_no), cls="text-center")
                                        # Conditionally hide Product columns
                                        if not specific_product_name:
                                            tags.td(prod_code)
                                            tags.td(prod_name)
                                        tags.td(f"{qty:,.2f}", cls="text-right")
                                        tags.td(f"{unit_price:,.2f}", cls="text-right")
                                        tags.td(f"{amount:,.2f}", cls="text-right")
                                
                                with tags.tr(cls="total-row"):
                                    # Adjust colspan based on visible columns
                                    colspan = 2 if specific_product_name else 4
                                    tags.td("TOTALS", colspan=str(colspan), cls="text-right")
                                    tags.td(f"{total_qty:,.2f}", cls="text-right")
                                    tags.td("-", cls="text-right")
                                    tags.td(f"{total_amount:,.2f}", cls="text-right")

                    # ==========================================
                    # 2. SUPPLIER-WISE PURCHASE REPORT
                    # ==========================================
                    elif report_type == 'supplier_wise':
                        sorted_lines = sorted(purchase_lines, key=lambda l: l.purchase.party.name if (l.purchase and l.purchase.party) else 'Unknown')
                        grouped_suppliers = groupby(sorted_lines, key=lambda l: l.purchase.party if (l.purchase and l.purchase.party) else None)

                        for supplier, s_lines in grouped_suppliers:
                            supp_name = supplier.name if supplier else 'Unknown Supplier'
                            
                            if not specific_supplier_name:
                                tags.h3(supp_name, style="margin: 20px 0 8px 0; color: #111827; font-size: 12px; font-weight: bold;")
                            
                            with tags.table():
                                with tags.thead():
                                    with tags.tr():
                                        tags.th("Purchase Date", cls="text-center", style="width: 80px;")
                                        tags.th("Product Name")
                                        tags.th("Quantity Purchased", cls="text-right", style="width: 70px;")
                                        tags.th("Purchase Rate", cls="text-right", style="width: 80px;")
                                        tags.th("Total Purchase Amount", cls="text-right", style="width: 90px;")
                                with tags.tbody():
                                    sub_qty = Decimal('0.00')
                                    sub_amount = Decimal('0.00')
                                    for line in s_lines:
                                        p_date = line.purchase.purchase_date.strftime('%d-%b-%Y') if line.purchase and line.purchase.purchase_date else ''
                                        prod_name = line.product.name if line.product else (line.description or '')
                                        qty = Decimal(str(line.quantity or '0.0'))
                                        unit_price = Decimal(str(line.unit_price or '0.0'))
                                        amount = Decimal(str(line.amount or (qty * unit_price)))
                                        sub_qty += qty
                                        sub_amount += amount

                                        with tags.tr():
                                            tags.td(p_date, cls="text-center")
                                            tags.td(prod_name)
                                            tags.td(f"{qty:,.2f}", cls="text-right")
                                            tags.td(f"{unit_price:,.2f}", cls="text-right")
                                            tags.td(f"{amount:,.2f}", cls="text-right")

                                    row_label = "TOTALS" if specific_supplier_name else f"Total for {supp_name}"
                                    with tags.tr(cls="total-row"):
                                        tags.td(row_label, colspan="2", cls="text-right")
                                        tags.td(f"{sub_qty:,.2f}", cls="text-right")
                                        tags.td("-", cls="text-right")
                                        tags.td(f"{sub_amount:,.2f}", cls="text-right")

                    # ==========================================
                    # 3. PURCHASE RATE HISTORY REPORT
                    # ==========================================
                    elif report_type == 'rate_history':
                        sorted_lines = sorted(purchase_lines, key=lambda l: (l.product.id if l.product else 0, l.purchase.purchase_date if l.purchase else ''))
                        prev_rates = {}
                        
                        with tags.table():
                            with tags.thead():
                                with tags.tr():
                                    # Conditionally hide Product columns
                                    if not specific_product_name:
                                        tags.th("Product Code")
                                        tags.th("Product Name")
                                    tags.th("Supplier Name")
                                    tags.th("Purchase Date", cls="text-center")
                                    tags.th("Previous Purchase Rate", cls="text-right")
                                    tags.th("Current Purchase Rate", cls="text-right")
                            with tags.tbody():
                                for line in sorted_lines:
                                    prod_id = line.product.id if line.product else 0
                                    prod_code = line.product.code if line.product else ''
                                    prod_name = line.product.name if line.product else (line.description or '')
                                    supplier_name = line.purchase.party.name if line.purchase and line.purchase.party else ''
                                    p_date = line.purchase.purchase_date.strftime('%d-%b-%Y') if line.purchase and line.purchase.purchase_date else ''
                                    curr_rate = Decimal(str(line.unit_price or '0.0'))
                                    prev_rate = prev_rates.get(prod_id, Decimal('0.00'))

                                    with tags.tr():
                                        # Conditionally hide Product columns
                                        if not specific_product_name:
                                            tags.td(prod_code)
                                            tags.td(prod_name)
                                        tags.td(supplier_name)
                                        tags.td(p_date, cls="text-center")
                                        tags.td(f"{prev_rate:,.2f}" if prev_rate else "-", cls="text-right")
                                        tags.td(f"{curr_rate:,.2f}", cls="text-right")
                                    
                                    prev_rates[prod_id] = curr_rate

                    # ==========================================
                    # 4. GOODS RECEIVING NOTE (GRN) REPORT
                    # ==========================================
                    elif report_type == 'grn_report':
                        with tags.table():
                            with tags.thead():
                                with tags.tr():
                                    tags.th("GRN Date", cls="text-center")
                                    tags.th("GRN No.", cls="text-center")
                                    tags.th("Purchase Order No.")
                                    # Conditionally hide Supplier Name
                                    if not specific_supplier_name:
                                        tags.th("Supplier Name")
                                    tags.th("Product Code")
                                    tags.th("Product Name")
                                    tags.th("Qty Ordered", cls="text-right")
                                    tags.th("Qty Received", cls="text-right")
                                    tags.th("Pending Qty", cls="text-right")
                                    tags.th("Unit Rate", cls="text-right")
                                    tags.th("Total Amount", cls="text-right")
                            with tags.tbody():
                                for line in purchase_lines:
                                    po_no = line.purchase.number if line.purchase else ''
                                    supplier_name = line.purchase.party.name if line.purchase and line.purchase.party else ''
                                    prod_code = line.product.code if line.product else ''
                                    prod_name = line.product.name if line.product else (line.description or '')
                                    qty_ordered = Decimal(str(line.quantity or '0.0'))
                                    unit_rate = Decimal(str(line.unit_price or '0.0'))
                                    
                                    moves = getattr(line, 'moves', [])
                                    received_moves = [m for m in moves if getattr(m, 'state', '') == 'done']
                                    
                                    if received_moves:
                                        for m in received_moves:
                                            grn_date = m.effective_date.strftime('%d-%b-%Y') if getattr(m, 'effective_date', None) else ''
                                            shipment = getattr(m, 'shipment', None)
                                            grn_no = getattr(shipment, 'number', getattr(shipment, 'reference', getattr(shipment, 'rec_name', ''))) if shipment else ''
                                            qty_received = Decimal(str(m.quantity or '0.0'))
                                            pending_qty = qty_ordered - qty_received
                                            total_amt = qty_received * unit_rate

                                            with tags.tr():
                                                tags.td(grn_date, cls="text-center")
                                                tags.td(grn_no, cls="text-center")
                                                tags.td(str(po_no))
                                                if not specific_supplier_name:
                                                    tags.td(supplier_name)
                                                tags.td(prod_code)
                                                tags.td(prod_name)
                                                tags.td(f"{qty_ordered:,.2f}", cls="text-right")
                                                tags.td(f"{qty_received:,.2f}", cls="text-right")
                                                tags.td(f"{pending_qty:,.2f}", cls="text-right")
                                                tags.td(f"{unit_rate:,.2f}", cls="text-right")
                                                tags.td(f"{total_amt:,.2f}", cls="text-right")
                                    else:
                                        with tags.tr():
                                            tags.td("-", cls="text-center")
                                            tags.td("Pending", cls="text-center")
                                            tags.td(str(po_no))
                                            if not specific_supplier_name:
                                                tags.td(supplier_name)
                                            tags.td(prod_code)
                                            tags.td(prod_name)
                                            tags.td(f"{qty_ordered:,.2f}", cls="text-right")
                                            tags.td("0.00", cls="text-right")
                                            tags.td(f"{qty_ordered:,.2f}", cls="text-right")
                                            tags.td(f"{unit_rate:,.2f}", cls="text-right")
                                            tags.td("0.00", cls="text-right")

                    # ==========================================
                    # 5. PURCHASE INVOICE REPORT
                    # ==========================================
                    elif report_type == 'purchase_invoice':
                        with tags.table():
                            with tags.thead():
                                with tags.tr():
                                    tags.th("Invoice Date", cls="text-center")
                                    tags.th("Invoice No.", cls="text-center")
                                    # Conditionally hide Supplier Name
                                    if not specific_supplier_name:
                                        tags.th("Supplier Name")
                                    tags.th("Purchase Order No.")
                                    tags.th("GRN No.", cls="text-center")
                                    tags.th("Product Name")
                                    tags.th("Qty Invoiced", cls="text-right")
                                    tags.th("Invoice Amount", cls="text-right")
                                    tags.th("Tax Amount", cls="text-right")
                                    tags.th("Payment Status", cls="text-center")
                            with tags.tbody():
                                for line in purchase_lines:
                                    po_no = line.purchase.number if line.purchase else ''
                                    prod_name = line.product.name if line.product else (line.description or '')
                                    
                                    inv_lines = getattr(line, 'invoice_lines', [])
                                    valid_invs = [il for il in inv_lines if getattr(il, 'invoice', None)]
                                    
                                    if valid_invs:
                                        for il in valid_invs:
                                            inv = il.invoice
                                            inv_date = inv.invoice_date.strftime('%d-%b-%Y') if getattr(inv, 'invoice_date', None) else ''
                                            inv_no = inv.number or inv.rec_name or ''
                                            supp_name = inv.party.name if getattr(inv, 'party', None) else ''
                                            qty_invoiced = Decimal(str(il.quantity or '0.0'))
                                            inv_amt = Decimal(str(il.amount or '0.0'))
                                            tax_amt = Decimal(str(inv.tax_amount or '0.0')) if hasattr(inv, 'tax_amount') else Decimal('0.00')
                                            pay_status = str(inv.state).title() if hasattr(inv, 'state') else ''

                                            grn_list = []
                                            direct_moves = getattr(il, 'stock_moves', [])
                                            for m in direct_moves:
                                                if getattr(m, 'state', '') == 'done' and getattr(m, 'shipment', None):
                                                    s_num = getattr(m.shipment, 'number', getattr(m.shipment, 'reference', getattr(m.shipment, 'rec_name', '')))
                                                    if s_num and s_num not in grn_list:
                                                        grn_list.append(s_num)
                                            
                                            if not grn_list:
                                                for m in getattr(line, 'moves', []):
                                                    if getattr(m, 'state', '') == 'done' and getattr(m, 'shipment', None):
                                                        s_num = getattr(m.shipment, 'number', getattr(m.shipment, 'reference', getattr(m.shipment, 'rec_name', '')))
                                                        if s_num and s_num not in grn_list:
                                                            grn_list.append(s_num)
                                                            
                                            grn_display = ", ".join(grn_list) if grn_list else "Pending"

                                            with tags.tr():
                                                tags.td(inv_date, cls="text-center")
                                                tags.td(inv_no, cls="text-center")
                                                if not specific_supplier_name:
                                                    tags.td(supp_name)
                                                tags.td(str(po_no))
                                                tags.td(grn_display, cls="text-center")
                                                tags.td(prod_name)
                                                tags.td(f"{qty_invoiced:,.2f}", cls="text-right")
                                                tags.td(f"{inv_amt:,.2f}", cls="text-right")
                                                tags.td(f"{tax_amt:,.2f}", cls="text-right")
                                                tags.td(pay_status, cls="text-center")
                                    else:
                                        with tags.tr():
                                            tags.td("-", cls="text-center")
                                            tags.td("Not Invoiced", cls="text-center")
                                            if not specific_supplier_name:
                                                tags.td(line.purchase.party.name if line.purchase and line.purchase.party else '')
                                            tags.td(str(po_no))
                                            
                                            moves = getattr(line, 'moves', [])
                                            grn_list = []
                                            for m in moves:
                                                if getattr(m, 'state', '') == 'done' and getattr(m, 'shipment', None):
                                                    s_num = getattr(m.shipment, 'number', getattr(m.shipment, 'reference', getattr(m.shipment, 'rec_name', '')))
                                                    if s_num and s_num not in grn_list:
                                                        grn_list.append(s_num)
                                            grn_display = ", ".join(grn_list) if grn_list else "Pending"
                                            
                                            tags.td(grn_display, cls="text-center")
                                            tags.td(prod_name)
                                            tags.td("0.00", cls="text-right")
                                            tags.td("0.00", cls="text-right")
                                            tags.td("0.00", cls="text-right")
                                            tags.td("Pending", cls="text-center")

        return doc.render()