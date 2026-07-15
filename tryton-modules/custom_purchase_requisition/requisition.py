from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval 

# --- 1. Core Requisition Extension ---
class PurchaseRequisition(metaclass=PoolMeta):
    __name__ = 'purchase.requisition'
    
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'launch_bulk_wizard_req': {
                'invisible': ~Eval('state').in_(['draft']),  # <-- 2. Change fields.Eval to Eval
                'depends': ['state'],
            }
        })

    @classmethod
    @ModelView.button_action('custom_purchase_requisition.wizard_bulk_add_req')
    def launch_bulk_wizard_req(cls, requisitions):
        pass

# --- 2. Relation Model for Multi-Select ---
class BulkAddReqStartProduct(ModelView):
    "Bulk Add Req Start - Product Relation"
    __name__ = 'purchase.requisition.bulk_add.start-product.product'
    
    start = fields.Many2One('purchase.requisition.bulk_add.start', "Start")
    product = fields.Many2One('product.product', "Product")

# --- 3. The Parent Wizard Model ---
class BulkAddReqStart(ModelView):
    "Bulk Add Requisition Start"
    __name__ = 'purchase.requisition.bulk_add.start'
    
    products = fields.Many2Many(
        'purchase.requisition.bulk_add.start-product.product',
        'start', 'product', "Products"
    )
    
    lines = fields.One2Many(
        'purchase.requisition.bulk_add.line', 'wizard_start', "Lines"
    )

    @fields.depends('products', 'lines')
    def on_change_products(self):
        pool = Pool()
        Line = pool.get('purchase.requisition.bulk_add.line')
        
        existing_lines = list(self.lines) if self.lines else []
        existing_product_ids = {
            line.product.id for line in existing_lines if getattr(line, 'product', None)
        }
        
        new_lines = []
        if self.products:
            for product in self.products:
                if product.id not in existing_product_ids:
                    line = Line()
                    line.product = product
                    line.unit = product.purchase_uom or product.default_uom                    
                    if product.product_suppliers:
                        line.supplier = product.product_suppliers[0].party
                        
                    new_lines.append(line)
                    existing_product_ids.add(product.id)
        
        self.lines = existing_lines + new_lines

# --- 4. The Child Model ---
class BulkAddReqLine(ModelView):
    "Bulk Add Requisition Lines"
    __name__ = 'purchase.requisition.bulk_add.line'
    
    wizard_start = fields.Many2One(
        'purchase.requisition.bulk_add.start', "Wizard Start"
    )
    product = fields.Many2One('product.product', "Product")
    quantity = fields.Float("Quantity", required=True)
    unit = fields.Many2One('product.uom', "Unit")
    supplier = fields.Many2One('party.party', "Supplier")

    unit_price = fields.Float("Unit Price")  # Optional by default
    amount = fields.Float("Amount")
    

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
            self.unit = self.product.purchase_uom or self.product.default_uom
            if self.product.product_suppliers:
                self.supplier = self.product.product_suppliers[0].party
        else:
            self.unit = None
            self.supplier = None

    @fields.depends('quantity', 'unit_price')
    def on_change_quantity(self):
        if self.quantity and self.unit_price:
            self.amount = self.quantity * self.unit_price
        else:
            self.amount = 0.0

    @fields.depends('quantity', 'unit_price')
    def on_change_unit_price(self):
        if self.quantity and self.unit_price:
            self.amount = self.quantity * self.unit_price
        else:
            self.amount = 0.0

# --- 5. The Wizard Controller ---
class BulkAddReq(Wizard):
    "Bulk Add Products to Requisition"
    __name__ = 'purchase.requisition.bulk_add'

    start = StateView('purchase.requisition.bulk_add.start',
        'custom_purchase_requisition.bulk_add_req_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Add to Requisition", 'add_lines', 'tryton-ok', default=True),
        ])
    
    add_lines = StateTransition()

    def transition_add_lines(self):
        pool = Pool()
        ReqLine = pool.get('purchase.requisition.line')
        Requisition = pool.get('purchase.requisition')
        
        requisition = Requisition(self.record.id)
        lines_to_save = []

        for w_line in getattr(self.start, 'lines', []): 
            if w_line.product and w_line.quantity and (w_line.quantity > 0):
                req_line = ReqLine()
                req_line.requisition = requisition
                req_line.product = w_line.product
                
                req_line.on_change_product()
                
                req_line.quantity = w_line.quantity
                if w_line.unit:
                    req_line.unit = w_line.unit
                if w_line.supplier:
                    req_line.supplier = w_line.supplier
                    
                lines_to_save.append(req_line)
        
        if lines_to_save:
            ReqLine.save(lines_to_save)
            
        return 'end'