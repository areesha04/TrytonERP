from trytond.pool import Pool
from .general_ledger import (
    GeneralLedgerReport,
    CashBookReport,
    PrintReportRCStart,
    PrintReportRC,
)

def register():
    Pool.register(
        PrintReportRCStart,
        module='custom_reports',
        type_='model',
    )
    Pool.register(
        GeneralLedgerReport,
        CashBookReport,
        module='custom_reports',
        type_='report',  # <--- MUST be 'report' for HTMLReport classes
    )
    Pool.register(
        PrintReportRC,
        module='custom_reports',
        type_='wizard',
    )