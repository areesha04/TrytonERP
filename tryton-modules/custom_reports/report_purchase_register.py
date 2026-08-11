from trytond.pool import Pool
from decimal import Decimal
import dominate.tags as tags

def generate_html(data):
    pool = Pool()
    PurchaseLine = pool.get('purchase.line')
    
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    product_id = data.get('product_id')

    domain = [
        ('purchase.purchase_date', '>=', start_date),
        ('purchase.purchase_date', '<=', end_date),
        ('purchase.state', 'in', ['processing', 'done'])
    ]
    if product_id:
        domain.append(('product', '=', product_id))
    
    lines = PurchaseLine.search(domain, order=[('purchase.purchase_date', 'ASC')])

    doc = tags.div(style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 12px; color: #333; padding: 20px 30px;")
    with doc:
        with tags.table(style="width: 100%; margin-bottom: 25px; border-collapse: collapse;"):
            with tags.tr():
                with tags.td(style="width: 60%; vertical-align: top; text-align: left;"):
                    tags.div("RAYS CREATIONS", style="font-size: 22px; font-weight: bold; margin-top: 8px; color: #2c3e50;")
                    tags.div("Bespoke Designs | Matchless Quality", style="font-size: 12px; font-style: italic; margin-bottom: 10px; color: #2c3e50;")
                with tags.td(style="width: 40%; vertical-align: top; text-align: right; padding-top: 15px;"):
                    tags.div(f"Period: {start_date} to {end_date}", style="font-weight: bold; color: #2c3e50;")

        tags.h2("PURCHASE REGISTER", style="margin: 0 0 20px 0; font-size: 20px; color: #e74c3c; border-bottom: 2px solid #e74c3c; padding-bottom: 5px;")

        with tags.table(style="width: 100%; border-collapse: collapse; margin-bottom: 25px;"):
            with tags.thead():
                with tags.tr(style="background-color: #2c3e50; color: #ffffff; text-align: left;"):
                    tags.th("Date", style="padding: 8px;")
                    tags.th("PO No.", style="padding: 8px;")
                    tags.th("Code", style="padding: 8px;")
                    tags.th("Product Name", style="padding: 8px;")
                    tags.th("Qty", style="padding: 8px; text-align: right;")
                    tags.th("Rate", style="padding: 8px; text-align: right;")
                    tags.th("Total", style="padding: 8px; text-align: right;")
            with tags.tbody():
                total_amount = Decimal('0.0')
                for index, line in enumerate(lines):
                    bg_color = "#f9f9f9" if index % 2 != 0 else "#ffffff"
                    prod = line.product
                    amount = line.quantity * line.unit_price if line.quantity and line.unit_price else Decimal('0.0')
                    total_amount += amount
                    
                    with tags.tr(style=f"background-color: {bg_color}; border-bottom: 1px solid #ecf0f1;"):
                        tags.td(str(line.purchase.purchase_date) if line.purchase else "", style="padding: 8px;")
                        tags.td(line.purchase.number if line.purchase else "", style="padding: 8px;")
                        tags.td(prod.code if prod else "", style="padding: 8px; color: #7f8c8d;")
                        tags.td(prod.name if prod else "", style="padding: 8px; font-weight: bold; color: #2c3e50;")
                        tags.td(str(line.quantity or 0), style="padding: 8px; text-align: right;")
                        tags.td(f"{line.unit_price:,.2f}" if line.unit_price else "0.00", style="padding: 8px; text-align: right;")
                        tags.td(f"{amount:,.2f}", style="padding: 8px; text-align: right; color: #e74c3c;")

                with tags.tr(style="border-top: 2px solid #2c3e50; font-weight: bold;"):
                    tags.td("GRAND TOTAL", colspan="6", style="padding: 10px; text-align: right; color: #2c3e50;")
                    tags.td(f"{total_amount:,.2f}", style="padding: 10px; text-align: right; color: #e74c3c;")

    return doc.render()