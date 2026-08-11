from trytond.pool import Pool
from .account import Account, QuickAccountEntry, MultiExpenseEntry, MultiExpenseEntryLine, MoveLine

def register():
    Pool.register(
        Account,
        QuickAccountEntry,
        MultiExpenseEntry,
        MultiExpenseEntryLine,
        MoveLine,
        module='custom_account_entries', type_='model')