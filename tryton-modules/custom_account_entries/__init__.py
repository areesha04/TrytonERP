from trytond.pool import Pool
from .account import QuickAccountEntry, Account

def register():
    Pool.register(
        Account,
        QuickAccountEntry,
        module='custom_account_entries', type_='model')