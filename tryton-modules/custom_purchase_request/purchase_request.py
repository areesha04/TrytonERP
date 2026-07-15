# from trytond.model import ModelView, fields
# from trytond.wizard import Wizard, StateView, StateTransition, Button
# from trytond.pool import Pool
# from trytond.transaction import Transaction

# class BulkAskPartiesStart(ModelView):
#     "Set Supplier"  # <--- Updated description
#     __name__ = 'purchase.request.bulk_ask_parties.start'
    
#     party = fields.Many2One('party.party', "Supplier", required=True)

# class BulkAskParties(Wizard):
#     "Set Supplier"  # <--- Updated description
#     __name__ = 'purchase.request.bulk_ask_parties'
    
#     start = StateView('purchase.request.bulk_ask_parties.start',
#         'custom_purchase_request.bulk_ask_parties_form', [
#             Button("Cancel", 'end', 'tryton-cancel'),
#             Button("Assign", 'assign', 'tryton-ok', default=True),
#         ])
#     assign = StateTransition()

#     def transition_assign(self):
#         pool = Pool()
#         Request = pool.get('purchase.request')
        
#         active_ids = Transaction().context.get('active_ids', [])
#         if active_ids:
#             requests = Request.browse(active_ids)
#             for req in requests:
#                 if req.state in ('draft', 'exception'):
#                     req.party = self.start.party
            
#             Request.save(requests)
            
#         return 'end'
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool
from trytond.transaction import Transaction

class BulkAskPartiesStart(ModelView):
    "Set Supplier"
    __name__ = 'purchase.request.bulk_ask_parties.start'
    
    party = fields.Many2One('party.party', "Supplier", required=True)
    
    # The read-only list of selected products
    lines = fields.One2Many(
        'purchase.request.bulk_ask_parties.line', 'start', 
        "Selected Products", readonly=True
    )

class BulkAskPartiesLine(ModelView):
    "Selected Product Line"
    __name__ = 'purchase.request.bulk_ask_parties.line'
    
    start = fields.Many2One('purchase.request.bulk_ask_parties.start', "Start")
    product = fields.Many2One('product.product', "Product")
    quantity = fields.Float("Quantity")

class BulkAskParties(Wizard):
    "Set Supplier"
    __name__ = 'purchase.request.bulk_ask_parties'
    
    start = StateView('purchase.request.bulk_ask_parties.start',
        'custom_purchase_request.bulk_ask_parties_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Assign", 'assign', 'tryton-ok', default=True),
        ])
    assign = StateTransition()

    def default_start(self, fields_names):
        # This runs automatically when the wizard opens.
        # It grabs your selected items and puts them in the read-only grid.
        pool = Pool()
        Request = pool.get('purchase.request')
        active_ids = Transaction().context.get('active_ids', [])
        
        res = {}
        if active_ids:
            requests = Request.browse(active_ids)
            lines = []
            for req in requests:
                lines.append({
                    'product': req.product.id if req.product else None,
                    'quantity': req.quantity,
                })
            res['lines'] = lines
        return res

    def transition_assign(self):
        pool = Pool()
        Request = pool.get('purchase.request')
        
        active_ids = Transaction().context.get('active_ids', [])
        if active_ids:
            requests = Request.browse(active_ids)
            for req in requests:
                if req.state in ('draft', 'exception'):
                    req.party = self.start.party
            
            Request.save(requests)
            
        return 'end'