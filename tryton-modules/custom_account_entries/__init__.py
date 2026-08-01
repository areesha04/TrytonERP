from trytond.pool import Pool
from .account import QuickAccountEntry

def register():
    Pool.register(
        QuickAccountEntry,
        module='custom_account_entries', type_='model')