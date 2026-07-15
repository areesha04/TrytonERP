from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta

# --- 1. Core Shipment Extension (Unchanged) ---
class ShipmentInternal(metaclass=PoolMeta):
    __name__ = 'stock.shipment.internal'
    
    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({'launch_bulk_wizard': {}})

    @classmethod
    @ModelView.button_action('custom_stock.wizard_bulk_add')
    def launch_bulk_wizard(cls, shipments):
        pass

# --- 2. NEW: Relation Model for Multi-Select ---
class BulkAddShipmentStartProduct(ModelView):
    "Bulk Add Start - Product Relation"
    __name__ = 'stock.shipment.internal.bulk_add.start-product.product'
    
    start = fields.Many2One('stock.shipment.internal.bulk_add.start', "Start")
    product = fields.Many2One('product.product', "Product")

# --- 3. UPDATED: The Parent Wizard Model ---
class BulkAddShipmentStart(ModelView):
    "Bulk Add Shipment Start"
    __name__ = 'stock.shipment.internal.bulk_add.start'
    
    # The new Multi-Select field
    products = fields.Many2Many(
        'stock.shipment.internal.bulk_add.start-product.product',
        'start', 'product', "Products"
    )
    
    # The existing Grid field
    lines = fields.One2Many(
        'stock.shipment.internal.bulk_add.line', 'wizard_start', "Lines"
    )

    # The trigger that copies selected products down into the grid
    @fields.depends('products', 'lines')
    def on_change_products(self):
        pool = Pool()
        Line = pool.get('stock.shipment.internal.bulk_add.line')
        
        existing_lines = list(self.lines) if self.lines else []
        
        # Track what is already in the grid so we don't create duplicates
        existing_product_ids = {
            line.product.id for line in existing_lines if getattr(line, 'product', None)
        }
        
        new_lines = []
        if self.products:
            for product in self.products:
                if product.id not in existing_product_ids:
                    # Instantiate a new grid row for each selected product
                    line = Line()
                    line.product = product
                    line.unit = product.default_uom
                    line.quantity = 0.0
                    new_lines.append(line)
                    
                    existing_product_ids.add(product.id)
        
        # Combine existing lines with the newly generated ones
        self.lines = existing_lines + new_lines

# --- 4. The Child Model (Unchanged) ---
class BulkAddShipmentLine(ModelView):
    "Bulk Add Shipment Lines"
    __name__ = 'stock.shipment.internal.bulk_add.line'
    
    wizard_start = fields.Many2One(
        'stock.shipment.internal.bulk_add.start', "Wizard Start"
    )
    product = fields.Many2One('product.product', "Product")
    quantity = fields.Float("Quantity")
    unit = fields.Many2One('product.uom', "Unit")
    
    @classmethod
    def default_quantity(cls):
        return 0.0

    @fields.depends('product')
    def on_change_product(self):
        if self.product:
            self.unit = self.product.default_uom
        else:
            self.unit = None

# --- 5. The Wizard Controller (Unchanged) ---
class BulkAddShipment(Wizard):
    "Bulk Add Products to Internal Shipment"
    __name__ = 'stock.shipment.internal.bulk_add'

    start = StateView('stock.shipment.internal.bulk_add.start',
        'custom_stock.bulk_add_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Add to Shipment", 'add_moves', 'tryton-ok', default=True),
        ])
    
    add_moves = StateTransition()

    def transition_add_moves(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Shipment = pool.get('stock.shipment.internal')
        
        shipment = Shipment(self.record.id)
        moves_to_save = []

        for line in getattr(self.start, 'lines', []): 
            if line.product and line.quantity and (line.quantity > 0):
                move = Move()
                move.company = shipment.company
                move.from_location = shipment.from_location
                move.to_location = shipment.to_location
                move.product = line.product
                move.quantity = line.quantity
                move.shipment = shipment
                
                if hasattr(line, 'unit') and line.unit:
                    move.unit = line.unit
                else:
                    move.unit = line.product.default_uom
                    
                moves_to_save.append(move)
        
        if moves_to_save:
            Move.save(moves_to_save)
            
        return 'end'