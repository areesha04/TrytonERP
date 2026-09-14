# sale.py
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval

class WebOrder(ModelSQL, ModelView):
    'Temporary Web Order'
    __name__ = 'sale.web.order'
    
    number = fields.Char('Web Order ID', readonly=True)
    party = fields.Many2One('party.party', 'Customer', required=True,
        states={'readonly': Eval('state') != 'draft'})
    currency = fields.Many2One('currency.currency', 'Foreign Currency', required=True,
        states={'readonly': Eval('state') != 'draft'})
    total_amount = fields.Numeric('Total Amount', states={'readonly': Eval('state') != 'draft'})
    
    lines = fields.One2Many('sale.web.order.line', 'web_order', 'Order Lines',
        states={'readonly': Eval('state') != 'draft'})
    
    state = fields.Selection([
        ('draft', 'Draft (Pending Review)'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], 'State', readonly=True, required=True, sort=False)

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'approve': {
                'invisible': Eval('state') != 'draft',
            },
            'cancel': {
                'invisible': Eval('state') != 'draft',
            },
        })

    @classmethod
    @ModelView.button
    def approve(cls, orders):
        """Validates the web order and converts it into a standard Tryton Sales Order"""
        pool = Pool()
        Sale = pool.get('sale.sale')
        
        sales_to_create = []
        for order in orders:
            # Map lines from web order to standard sale lines
            sale_lines = []
            for line in order.lines:
                sale_lines.append(('create', [{
                    'product': line.product.id,
                    'quantity': line.quantity,
                    'unit_price': line.unit_price,
                }]))

            sales_to_create.append({
                'party': order.party.id,
                'currency': order.currency.id,
                'sale_date': fields.Date.today(),
                'lines': sale_lines,
                # Add any custom fields you need here (e.g., origin reference)
                'origin': f"Web Order: {order.number}",
            })
            order.state = 'approved'
            
        if sales_to_create:
            Sale.create(sales_to_create)

    @classmethod
    @ModelView.button
    def cancel(cls, orders):
        for order in orders:
            order.state = 'cancelled'
        cls.save(orders)


class WebOrderLine(ModelSQL, ModelView):
    'Temporary Web Order Line'
    __name__ = 'sale.web.order.line'
    
    web_order = fields.Many2One('sale.web.order', 'Web Order', required=True, ondelete='CASCADE')
    product = fields.Many2One('product.product', 'Product', required=True, domain=[('type', '!=', 'service')])
    quantity = fields.Float('Quantity', required=True)
    unit_price = fields.Numeric('Unit Price', required=True)