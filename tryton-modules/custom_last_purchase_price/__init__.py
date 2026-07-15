from trytond.pool import Pool
from .purchase_requisition import PurchaseRequisitionLine

def register():
    Pool.register(
        PurchaseRequisitionLine,
        module='custom_last_purchase_price', type_='model'
    )