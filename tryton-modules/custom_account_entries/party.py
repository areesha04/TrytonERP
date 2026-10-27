from trytond.pool import PoolMeta
from trytond.model import fields

class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    account_title = fields.Char("Account Title")
    account_number = fields.Char("Account Number")