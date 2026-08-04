from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction

class Account(metaclass=PoolMeta):
    __name__ = 'account.account'
    
    is_quick_entry_bank = fields.Boolean('Quick Entry Bank/Cash')

class QuickAccountEntry(ModelSQL, ModelView):
    "Rays Creations Quick Account Entry"
    __name__ = 'custom.account.quick_entry'
    
    company = fields.Many2One('company.company', 'Company', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    effective_date = fields.Date('Effective Date', required=True)
    
    period = fields.Many2One('account.period', 'Period', required=True,
        domain=[('company', '=', Eval('company', -1))],
        depends=['company', 'effective_date'])
        
    description = fields.Char('Description')
    
    entry_type = fields.Selection([
        ('payment', 'Cash/Bank Disbursement'),
        ('transfer', 'Bank to Cash Transfer'),
    ], 'Entry Type', required=True)

    from_account = fields.Many2One('account.account', 'From Account',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('is_quick_entry_bank', '=', True) # No more hardcoding
        ],
        depends=['company'],
        required=True)

    to_account = fields.Many2One('account.account', 'To Account',
        domain=[
            ('company', '=', Eval('company', -1)),
            If(Eval('entry_type') == 'transfer',
                ('is_quick_entry_bank', '=', True), # No more hardcoding
                ('closed', '!=', True)
            )
        ],
        depends=['company', 'entry_type'],
        required=True)

    party_required = fields.Function(fields.Boolean('Party Required'), 'on_change_with_party_required')

    party = fields.Many2One('party.party', 'Party',
        states={
            'invisible': Eval('entry_type') == 'transfer',
            'required': Eval('party_required', False)
        },
        depends=['entry_type', 'party_required'])

    amount = fields.Numeric('Amount', required=True)

    move = fields.Many2One('account.move', 'Generated Move', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], 'State', readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
            'process_entry': {
                'invisible': Eval('state') == 'done',
                'depends': ['state'],
            }
        })

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_entry_type(cls):
        return 'payment'

    @classmethod
    def default_effective_date(cls):
        return Pool().get('ir.date').today()

    @classmethod
    def default_period(cls):
        Period = Pool().get('account.period')
        company_id = Transaction().context.get('company')
        if company_id:
            today = Pool().get('ir.date').today()
            period = Period.find(company_id, date=today)
            if period:
                return period.id
        return None

    @fields.depends('entry_type')
    def on_change_entry_type(self):
        self.from_account = None
        self.to_account = None
        self.amount = None
        self.party = None

    @fields.depends('effective_date', 'company')
    def on_change_effective_date(self):
        if self.effective_date and self.company:
            Period = Pool().get('account.period')
            period = Period.find(self.company.id, date=self.effective_date)
            if period:
                self.period = period.id
            else:
                self.period = None

    @fields.depends('to_account')
    def on_change_with_party_required(self, name=None):
        if self.to_account:
            return self.to_account.party_required
        return False

    @classmethod
    @ModelView.button
    def process_entry(cls, records):
        Move = Pool().get('account.move')
        Line = Pool().get('account.move.line')
        
        for record in records:
            if record.state == 'done':
                continue
                
            if record.from_account.id == record.to_account.id:
                cls.raise_user_error("The 'From' and 'To' accounts cannot be identical.")

            if not record.period:
                cls.raise_user_error(f"No open period found for date {record.effective_date}.")

            move = Move(
                journal=record.journal,
                period=record.period,
                date=record.effective_date,
                company=record.company,
                description=record.description
            )
            move.save()

            lines_to_create = [{
                'move': move.id,
                'account': record.from_account.id,
                'credit': record.amount,
                'debit': 0,
                'description': record.description,
            }, {
                'move': move.id,
                'account': record.to_account.id,
                'credit': 0,
                'debit': record.amount,
                'party': record.party.id if record.party else None,
                'description': record.description,
            }]
                
            Line.create(lines_to_create)
            Move.post([move])
                
            record.move = move
            record.state = 'done'
            record.save()