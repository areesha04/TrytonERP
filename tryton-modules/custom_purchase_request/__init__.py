# from trytond.pool import Pool
# from .purchase_request import BulkAskPartiesStart, BulkAskParties

# def register():
#     Pool.register(
#         BulkAskPartiesStart,
#         module='custom_purchase_request', type_='model'
#     )
#     Pool.register(
#         BulkAskParties,
#         module='custom_purchase_request', type_='wizard'
#     )

from trytond.pool import Pool
from .purchase_request import BulkAskPartiesStart, BulkAskPartiesLine, BulkAskParties

def register():
    Pool.register(
        BulkAskPartiesStart,
        BulkAskPartiesLine,
        module='custom_purchase_request', type_='model'
    )
    Pool.register(
        BulkAskParties,
        module='custom_purchase_request', type_='wizard'
    )