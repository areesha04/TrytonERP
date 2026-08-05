from trytond.pool import Pool
from .account import Account, QuickAccountEntry, MultiExpenseEntry, MultiExpenseEntryLine

def register():
    Pool.register(
        Account,
        QuickAccountEntry,
        MultiExpenseEntry,
        MultiExpenseEntryLine,
        module='custom_account_entries', type_='model')