from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction
from decimal import Decimal

class Account(metaclass=PoolMeta):
    __name__ = 'account.account'
    is_quick_entry_bank = fields.Boolean('Fund Transfer Bank/Cash')

class MoveLine(metaclass=PoolMeta):
    __name__ = 'account.move.line'
    
    # This stores the party strictly for your reporting without breaking the ledger
    custom_party = fields.Many2One('party.party', 'Record Party')

# ==========================================
# TOOL 1: INTERNAL FUND TRANSFERS ONLY
# ==========================================
class QuickAccountEntry(ModelSQL, ModelView):
    "Bank to Cash Transfer Entry"
    __name__ = 'custom.account.quick_entry'
    
    company = fields.Many2One('company.company', 'Company', required=True,
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    effective_date = fields.Date('Effective Date', required=True,
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[('company', '=', Eval('company', -1))],
        depends=['company', 'effective_date', 'state'],
        states={'readonly': Eval('state') == 'done'})
    description = fields.Char('Description',
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    
    from_account = fields.Many2One('account.account', 'From Account',
        domain=[('company', '=', Eval('company', -1)), ('is_quick_entry_bank', '=', True)],
        depends=['company', 'state'], required=True,
        states={'readonly': Eval('state') == 'done'})

    to_account = fields.Many2One('account.account', 'To Account',
        domain=[('company', '=', Eval('company', -1)), ('is_quick_entry_bank', '=', True)],
        depends=['company', 'state'], required=True,
        states={'readonly': Eval('state') == 'done'})

    amount = fields.Numeric('Amount', required=True,
        states={'readonly': Eval('state') == 'done'}, depends=['state'])

    move = fields.Many2One('account.move', 'Generated Move', readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({'process_entry': {'invisible': Eval('state') == 'done', 'depends': ['state']}})

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_effective_date(cls):
        return Pool().get('ir.date').today()

    @classmethod
    def default_journal(cls):
        Journal = Pool().get('account.journal')
        journals = Journal.search([
            'OR',
            ('type', '=', 'cash'),
            ('name', 'ilike', '%cash%')
        ], limit=1)
        if journals:
            return journals[0].id
        return None

    @fields.depends('effective_date', 'company')
    def on_change_effective_date(self):
        if self.effective_date and self.company:
            Period = Pool().get('account.period')
            period = Period.find(self.company.id, date=self.effective_date)
            self.period = period.id if period else None

    @classmethod
    @ModelView.button
    def process_entry(cls, records):
        Move = Pool().get('account.move')
        Line = Pool().get('account.move.line')
        for record in records:
            if record.state == 'done': continue
            if record.from_account.id == record.to_account.id:
                cls.raise_user_error("The 'From' and 'To' accounts cannot be identical.")

            move = Move(
                journal=record.journal, period=record.period, date=record.effective_date,
                company=record.company, description=record.description
            )
            move.save()

            Line.create([{
                'move': move.id, 'account': record.from_account.id,
                'credit': record.amount, 'debit': 0, 'description': record.description,
            }, {
                'move': move.id, 'account': record.to_account.id,
                'credit': 0, 'debit': record.amount, 'description': record.description,
            }])
            Move.post([move])
            record.move = move
            record.state = 'done'
            record.save()

    move_number = fields.Function(
        fields.Char('Move Number', readonly=True), 'get_move_number'
    )

    def get_move_number(self, name):
        return self.move.number if self.move else ''


# ==========================================
# TOOL 2: MULTI-EXPENSE DISBURSEMENTS
# ==========================================
class MultiExpenseEntry(ModelSQL, ModelView):
    "Consolidated Payment Entry"
    __name__ = 'custom.account.multi_expense'
    
    company = fields.Many2One('company.company', 'Company', required=True,
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    journal = fields.Many2One('account.journal', 'Journal', required=True,
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    effective_date = fields.Date('Effective Date', required=True,
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[('company', '=', Eval('company', -1))],
        depends=['company', 'effective_date', 'state'],
        states={'readonly': Eval('state') == 'done'})
    description = fields.Char('Description',
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    
    from_account = fields.Many2One('account.account', 'Payment Account (Bank/Cash)',
        domain=[('company', '=', Eval('company', -1)), ('is_quick_entry_bank', '=', True)],
        depends=['company', 'state'], required=True,
        states={'readonly': Eval('state') == 'done'})
        
    lines = fields.One2Many('custom.account.multi_expense.line', 'entry', 'Expense Lines',
        states={'readonly': Eval('state') == 'done'}, depends=['state'])
    
    total_amount = fields.Function(fields.Numeric('Total Amount'), 'get_total_amount')
    
    move = fields.Many2One('account.move', 'Generated Move', readonly=True)
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({'process_entry': {'invisible': Eval('state') == 'done', 'depends': ['state']}})

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_effective_date(cls):
        return Pool().get('ir.date').today()

    @classmethod
    def default_journal(cls):
        Journal = Pool().get('account.journal')
        journals = Journal.search([
            'OR',
            ('type', '=', 'cash'),
            ('name', 'ilike', '%cash%')
        ], limit=1)
        if journals:
            return journals[0].id
        return None
        
    def get_total_amount(self, name):
        return sum(line.amount for line in self.lines if line.amount) or Decimal('0.0')

    @fields.depends('effective_date', 'company')
    def on_change_effective_date(self):
        if self.effective_date and self.company:
            Period = Pool().get('account.period')
            period = Period.find(self.company.id, date=self.effective_date)
            self.period = period.id if period else None

    @classmethod
    @ModelView.button
    def process_entry(cls, records):
        Move = Pool().get('account.move')
        Line = Pool().get('account.move.line')
        for record in records:
            if record.state == 'done': continue
            if not record.lines:
                cls.raise_user_error("You must add at least one expense line.")

            move = Move(
                journal=record.journal, period=record.period, date=record.effective_date,
                company=record.company, description=record.description
            )
            move.save()

            lines_to_create = []
            total = Decimal('0.0')
            
            # Create individual Debit lines from the grid
            for exp_line in record.lines:
                total += exp_line.amount
                
                # --- NEW LOGIC: Route the party safely ---
                native_party = None
                custom_party = None
                
                if exp_line.party:
                    if exp_line.account.party_required:
                        # Standard accounting requires it (e.g., Payables)
                        native_party = exp_line.party.id
                    else:
                        # Record purposes only (e.g., Expenses)
                        custom_party = exp_line.party.id

                lines_to_create.append({
                    'move': move.id,
                    'account': exp_line.account.id,
                    'party': native_party,
                    'custom_party': custom_party, 
                    'credit': Decimal('0.0'), 
                    'debit': exp_line.amount,
                    'description': exp_line.description or record.description,
                })
                
            # Create the SINGLE consolidated Credit line for the Bank/Cash account
            lines_to_create.append({
                'move': move.id,
                'account': record.from_account.id,
                'party': None,      # Ensure native party is empty for bank
                'custom_party': None,   # Leave empty for bank
                'credit': total,
                'debit': Decimal('0.0'), 
                'description': record.description,
            })

            Line.create(lines_to_create)
            Move.post([move])
            record.move = move
            record.state = 'done'
            record.save()

    move_number = fields.Function(
        fields.Char('Move Number', readonly=True), 'get_move_number'
    )

    def get_move_number(self, name):
        return self.move.number if self.move else ''


class MultiExpenseEntryLine(ModelSQL, ModelView):
    "Expense Line"
    __name__ = 'custom.account.multi_expense.line'
    
    entry = fields.Many2One('custom.account.multi_expense', 'Entry', required=True, ondelete='CASCADE')
    account = fields.Many2One('account.account', 'Account', required=True, domain=[('closed', '!=', True)])
    description = fields.Char('Line Description')
    
    party_required = fields.Function(fields.Boolean('Party Required'), 'on_change_with_party_required')
    party = fields.Many2One('party.party', 'Party', 
        states={'required': Eval('party_required', False)}, depends=['party_required'])
        
    amount = fields.Numeric('Amount', required=True)

    @fields.depends('account')
    def on_change_with_party_required(self, name=None):
        if self.account:
            return self.account.party_required
        return False