from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from weasyprint import HTML as WeasyHTML

from .procurement_report_base import ProcurementCustomReport

class ProcurementReportStart(ModelView):
    'Procurement Report Wizard Start'
    __name__ = 'custom.procurement.report.start'

    report_type = fields.Selection([
        ('purchase_register', 'Purchase Register'),
        ('supplier_wise', 'Supplier-wise Purchase Report'),
        ('rate_history', 'Purchase Rate History Report'),
        ('grn_report', 'Goods Receiving Note (GRN) Report'),
        ('purchase_invoice', 'Purchase Invoice Report'),
    ], 'Report Type', required=True)
    
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    
    supplier = fields.Many2One('party.party', 'Supplier', states={
        'invisible': Eval('report_type').in_(['purchase_register', 'rate_history'])
    }, depends=['report_type'])

    product = fields.Many2One('product.product', 'Product', states={
        'invisible': ~Eval('report_type').in_(['purchase_register', 'rate_history'])
    }, depends=['report_type'])

    @staticmethod
    def default_report_type():
        return 'purchase_register'


class ProcurementReportWizard(Wizard):
    'Procurement Reports Wizard'
    __name__ = 'custom.procurement.report.wizard'

    start = StateView('custom.procurement.report.start',
        'custom_reports.procurement_report_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Download PDF', 'generate', 'tryton-print', default=True),
        ])
    
    generate = StateAction('custom_reports.act_preview_url')

    def do_generate(self, action):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        
        # 1. Validate Dates
        if self.start.start_date > self.start.end_date:
            raise UserError("The Start Date cannot be later than the End Date.")
        
        # 2. Enrich Data Dictionary for the HTML Report
        data = {
            'report_type': self.start.report_type,
            'start_date': self.start.start_date,  # Pass raw Date object, format in HTML class
            'end_date': self.start.end_date,
            'supplier_id': self.start.supplier.id if self.start.supplier else None,
            'supplier_name': self.start.supplier.name if self.start.supplier else "All Suppliers",
            'product_id': self.start.product.id if self.start.product else None,
            'product_name': self.start.product.name if self.start.product else "All Products",
            'company_name': 'Rays Creations'
        }
        
        # 3. Generate HTML Content
        html_content = ProcurementCustomReport.get_html([], data)
        
        # 4. Render PDF using WeasyPrint
        pdf_bytes = WeasyHTML(string=html_content).write_pdf()
        
        # 5. Format Filename
        safe_type = self.start.report_type.replace('_', '-')
        filename = f"procurement_{safe_type}_{self.start.start_date}_to_{self.start.end_date}.pdf"
        
        # 6. Save Attachment temporarily to the current user
        attachment = Attachment.create([{
            'name': filename,
            'type': 'data',
            'data': pdf_bytes,
            'resource': f"res.user,{Transaction().user}",
        }])[0]
        
        # 7. Pass URL to custom controller for browser preview/download
        db_name = Transaction().database.name
        action['url'] = f"/{db_name}/custom_reports/preview/{attachment.id}"
        
        return action, {}