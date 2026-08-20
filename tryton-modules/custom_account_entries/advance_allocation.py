from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.pool import Pool
from trytond.pyson import Eval, If
from decimal import Decimal

class AdvanceAllocation(Workflow, ModelSQL, ModelView):
    "Bulk Recall Deposit Allocation"
    __name__ = 'account.advance_allocation'

    party = fields.Many2One(
        'party.party', 'Supplier', required=True, 
        states={'readonly': Eval('state') == 'done'}
    )
    
    advance_account = fields.Many2One(
        'account.account', 'Advance Account', required=True,
        states={'readonly': Eval('state') == 'done'}
    )
    
    available_advance = fields.Function(
        fields.Numeric('Available Advance to Recall', digits=(16, 2)),
        'on_change_with_available_advance'
    )

    # --- NEW OPTIONS ---
    post_invoices = fields.Boolean(
        'Post Invoices', 
        states={'readonly': Eval('state') == 'done'}
    )
    # pay_invoices = fields.Boolean(
    #     'Pay / Reconcile', 
    #     states={'readonly': Eval('state') == 'done'}
    # )
    
    invoices = fields.Many2Many(
        'account.advance_allocation-account.invoice',
        'allocation', 'invoice', 'Supplier Invoices',
        domain=[
            ('party', '=', Eval('party')),
            ('type', '=', 'in'),
            # Restrict to Draft only when making the allocation.
            # Allow posted/paid states so the system doesn't crash after posting.
            If(Eval('state') == 'draft',
                ('state', '=', 'draft'),
                ('state', 'in', ['draft', 'posted', 'paid', 'cancelled'])
            ),
        ],
        states={'readonly': Eval('state') == 'done'},
        depends=['party', 'state']
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Recalled / Applied'),
    ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._transitions |= {
            ('draft', 'done'),
        }
        cls._buttons.update({
            'allocate': {
                'invisible': Eval('state') == 'done',
                'depends': ['state'],
            },
            'open_invoices': {},
        })

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_advance_account(cls):
        """ Automatically sets a default advance account based on code or name """
        pool = Pool()
        Account = pool.get('account.account')
        
        # Try to find your standard advance account by code or keyword
        accounts = Account.search([
            'OR',
            ('code', 'ilike', '1.9.9%'),
            ('name', 'ilike', '%Advance%')
        ], limit=1)
        
        return accounts[0].id if accounts else None

    @classmethod
    def default_post_invoices(cls):
        return True

    @classmethod
    def default_pay_invoices(cls):
        return True

    @fields.depends('party', 'advance_account')
    def on_change_with_available_advance(self, name=None):
        if not self.party or not self.advance_account:
            return Decimal('0.00')
            
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        
        lines = MoveLine.search([
            ('party', '=', self.party.id),
            ('account', '=', self.advance_account.id),
            ('reconciliation', '=', None),
        ])
        
        net_advance = sum((l.debit - l.credit) for l in lines)
        return net_advance if net_advance > 0 else Decimal('0.00')

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def allocate(cls, allocations):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Invoice = pool.get('account.invoice')
        Line = pool.get('account.move.line')

        for allocation in allocations:
            lines_to_save = []
            invoices_to_update = set()
            
            # Fetch unreconciled lines to get the available balance
            adv_lines = Line.search([
                ('party', '=', allocation.party.id),
                ('account', '=', allocation.advance_account.id),
                ('reconciliation', '=', None),
            ])
            
            net_available = sum((l.debit - l.credit) for l in adv_lines)
            if net_available <= 0:
                continue 
                
            for invoice in allocation.invoices:
                if invoice.state != 'draft':
                    cls.raise_user_error("You can only recall deposits into Draft invoices.")
                
                amount_needed = invoice.total_amount
                
                # Apply advance funds to the invoice
                if amount_needed > 0 and net_available > 0:
                    use_amount = min(amount_needed, net_available)
                    
                    line = InvoiceLine()
                    line.invoice = invoice
                    line.type = 'line'
                    line.account = allocation.advance_account
                    line.quantity = 1
                    line.unit_price = -use_amount
                    line.description = 'Recalled Advance Payment'
                    
                    lines_to_save.append(line)
                    invoices_to_update.add(invoice)
                    
                    net_available -= use_amount

            # Save lines, update taxes, and post the invoices if checked
            if lines_to_save:
                InvoiceLine.save(lines_to_save)
                Invoice.update_taxes(list(invoices_to_update))
                
                if allocation.post_invoices:
                    invoices_to_post = list(invoices_to_update)
                    try:
                        Invoice.validate_invoice(invoices_to_post)
                    except Exception:
                        pass
                    Invoice.post(invoices_to_post)
    @classmethod
    @ModelView.button
    def open_invoices(cls, allocations):
        invoice_ids = []
        for allocation in allocations:
            invoice_ids.extend([inv.id for inv in allocation.invoices])
            
        if not invoice_ids:
            return
            
        return {
            'type': 'ir.action.act_window',
            'name': 'Allocated Invoices',
            'res_model': 'account.invoice',
            'domain': [('id', 'in', invoice_ids)],
        }

class AllocationInvoiceRel(ModelSQL):
    "Allocation - Invoice Relation"
    __name__ = 'account.advance_allocation-account.invoice'
    allocation = fields.Many2One('account.advance_allocation', 'Allocation', ondelete='CASCADE', required=True)
    invoice = fields.Many2One('account.invoice', 'Invoice', ondelete='RESTRICT', required=True)