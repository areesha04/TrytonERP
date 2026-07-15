from trytond.pool import PoolMeta, Pool
from trytond.model import fields

class PurchaseRequisitionLine(metaclass=PoolMeta):
    __name__ = 'purchase.requisition.line'

    # 1. Change to a Function field. 
    # This tells Tryton: "Calculate this on the fly, don't store it in the database."
    last_purchase_price = fields.Function(
        fields.Numeric("Last Purchase Price"),
        'on_change_with_last_purchase_price'
    )

    # 2. Use Tryton's dedicated on_change_with decorator
    @fields.depends('product')
    def on_change_with_last_purchase_price(self, name=None):
        if getattr(self, 'product', None):
            pool = Pool()
            PurchaseLine = pool.get('purchase.line')
            
            lines = PurchaseLine.search([
                ('product', '=', self.product.id),
                ('purchase.state', 'in', ['confirmed', 'processing', 'done']),
            ], order=[('id', 'DESC')], limit=1)
            
            if lines:
                print("lines:",lines)
                return lines[0].unit_price
                
        # If no confirmed purchase is found, return None (which hides the column)
        return None