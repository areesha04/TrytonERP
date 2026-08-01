from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateAction, Button
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

class MoveTransferStart(ModelView):
    'Quick Account Transfer Start'
    __name__ = 'account.move.transfer.start'
    
    company = fields.Many2One('company.company', 'Company', required=True)
    journal = fields.Many2One('account.journal', 'Journal', required=True)
    date = fields.Date('Date', required=True)
    
    # NEW FIELD: Party
    party = fields.Many2One('party.party', 'Party')
    
    from_account = fields.Many2One(
        'account.account', 'From Account (Credit)', required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('type', '!=', None),
            ('closed', '!=', True),
        ])
        
    to_account = fields.Many2One(
        'account.account', 'To Account (Debit)', required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('type', '!=', None),
            ('closed', '!=', True),
        ])
    
    amount = fields.Numeric('Amount', required=True, digits=(16, 2))
    description = fields.Char('Description')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')
        
    @classmethod
    def default_date(cls):
        return Pool().get('ir.date').today()

class MoveTransfer(Wizard):
    'Quick Account Transfer'
    __name__ = 'account.move.transfer'
    
    start = StateView('account.move.transfer.start',
        'custom_account_transfer.transfer_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create Move', 'create_move', 'tryton-ok', default=True),
        ])
        
    create_move = StateAction('account.act_move_form')

    def do_create_move(self, action):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Period = pool.get('account.period')

        period = Period.find(self.start.company.id, date=self.start.date)

        move = Move()
        move.company = self.start.company
        move.journal = self.start.journal
        move.date = self.start.date
        move.period = period
        move.description = self.start.description

        line_from = Line()
        line_from.account = self.start.from_account
        line_from.credit = self.start.amount
        line_from.debit = 0
        line_from.description = self.start.description
        # ASSIGN PARTY HERE
        line_from.party = self.start.party 

        line_to = Line()
        line_to.account = self.start.to_account
        line_to.debit = self.start.amount
        line_to.credit = 0
        line_to.description = self.start.description
        # ASSIGN PARTY HERE
        line_to.party = self.start.party 

        move.lines = (line_from, line_to)
        move.save()

        action['pyson_domain'] = Eval('id') == move.id
        action['name'] = f"Transfer Move: {move.number or 'Draft'}"
        
        return action, {}