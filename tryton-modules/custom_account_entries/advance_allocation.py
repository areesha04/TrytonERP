from trytond.model import ModelView, ModelSQL, Workflow, fields
from trytond.pool import Pool
from trytond.pyson import Eval, If
from decimal import Decimal
from trytond.exceptions import UserError, UserWarning

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
        'allocation', 'invoice', 'Invoices',
        domain=[
            ('state', '=', 'posted'),          # 'posted' state natively implies it is not yet paid
            ('type', '=', 'in'),               # Supplier invoices
            ('party', '=', Eval('party')),     # Must belong to the selected party
        ],
        depends=['party']
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Recalled / Applied'),
    ], 'State', readonly=True)

    advance_lines = fields.Function(
        fields.One2Many('account.move.line', None, 'Advance & Recall History'),
        'on_change_with_advance_lines',
        setter='set_advance_lines'
    )

    # 2. Add this empty setter method to satisfy Tryton's ORM check
    @classmethod
    def set_advance_lines(cls, records, name, value):
        pass

    # (Do the same for net_available_amount just to be fully safe)
    net_available_amount = fields.Function(
        fields.Numeric('Remaining Balance', digits=(16, 2)),
        'on_change_with_net_available_amount',
        setter='set_net_available_amount'
    )

    @classmethod
    def set_net_available_amount(cls, records, name, value):
        pass
    @fields.depends('party', 'advance_account')
    def on_change_with_advance_lines(self, name=None):
        pool = Pool()
        Line = pool.get('account.move.line')
        
        if self.party and self.advance_account:
            # Fetches BOTH Debits (Advances) and Credits (Recalls)
            lines = Line.search([
                ('party', '=', self.party.id),
                ('account', '=', self.advance_account.id),
                ('reconciliation', '=', None),
            ])
            return [line.id for line in lines]
        return []

    @fields.depends('party', 'advance_account')
    def on_change_with_net_available_amount(self, name=None):
        pool = Pool()
        Line = pool.get('account.move.line')
        
        if self.party and self.advance_account:
            lines = Line.search([
                ('party', '=', self.party.id),
                ('account', '=', self.advance_account.id),
                ('reconciliation', '=', None),
            ])
            # Calculates the exact final balance (e.g., 9,050.00)
            net = sum((l.debit - l.credit) for l in lines)
            return net
            
        return Decimal('0.00')
        
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
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Journal = pool.get('account.journal')
        Date = pool.get('ir.date')

        # Fetch a default journal for the accounting moves (e.g., General Journal)
        journals = Journal.search([('type', '=', 'general')], limit=1)
        if not journals:
            raise UserError("No General Journal found to process the allocation.")
        journal = journals[0]

        for allocation in allocations:
            # 1. Calculate available advance
            adv_lines = Line.search([
                ('party', '=', allocation.party.id),
                ('account', '=', allocation.advance_account.id),
                ('reconciliation', '=', None),
            ])
            net_available = sum((l.debit - l.credit) for l in adv_lines)

            if net_available <= 0:
                continue 

            for invoice in allocation.invoices:
                if invoice.state != 'posted':
                    continue
                
                amount_needed = invoice.amount_to_pay
                
                if amount_needed > 0 and net_available > 0:
                    use_amount = min(amount_needed, net_available)
                    
                    # 2. Create the Payment Move (Journal Entry)
                    move = Move()
                    move.journal = journal
                    move.date = Date.today()
                    move.company = invoice.company 
                    
                    # Line A: Reduce the Advance Balance (Credit)
                    line_adv = Line()
                    line_adv.account = allocation.advance_account
                    line_adv.party = allocation.party
                    line_adv.credit = use_amount
                    line_adv.debit = 0
                    
                    # Line B: Pay the Supplier Invoice (Debit)
                    line_pay = Line()
                    line_pay.account = invoice.account
                    line_pay.party = allocation.party
                    line_pay.debit = use_amount
                    line_pay.credit = 0
                    
                    move.lines = (line_adv, line_pay)
                    move.save()
                    
                    # Post the journal entry immediately
                    Move.post([move])
                    
                    # 3. Fetch the fully-loaded line from the database
                    saved_lines = Line.search([
                        ('move', '=', move),
                        ('account', '=', invoice.account),
                        ('debit', '>', 0)
                    ])
                    
                    # 4. Reconcile the fetched payment line with the invoice line
                    lines_to_reconcile = saved_lines + list(invoice.lines_to_pay)
                    
                    if use_amount == amount_needed:
                        # Full payment: link them permanently
                        Line.reconcile(lines_to_reconcile)
                    else:
                        raise UserError("Insufficient Advance: The remaining advance balance is not enough to fully pay the invoice(s). You can only use this feature if the advance covers the entire invoice(s) amount.")
                    net_available -= use_amount
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