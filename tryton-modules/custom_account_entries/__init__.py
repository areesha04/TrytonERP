from trytond.pool import Pool
from .account import Account, QuickAccountEntry, MultiExpenseEntry, MultiExpenseEntryLine, MoveLine
from . import advance_allocation
from . import party

def register():
    Pool.register(
        Account,
        QuickAccountEntry,
        MultiExpenseEntry,
        MultiExpenseEntryLine,
        MoveLine,
        advance_allocation.AdvanceAllocation,
        advance_allocation.AllocationInvoiceRel,
        party.Party,
        module='custom_account_entries', type_='model')