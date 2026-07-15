from trytond.pool import Pool
from .requisition import (
    PurchaseRequisition, 
    BulkAddReqStartProduct, 
    BulkAddReqStart, 
    BulkAddReqLine, 
    BulkAddReq
)

def register():
    Pool.register(
        PurchaseRequisition,
        BulkAddReqStartProduct,
        BulkAddReqStart,
        BulkAddReqLine,
        module='custom_purchase_requisition', type_='model'
    )
    Pool.register(
        BulkAddReq,
        module='custom_purchase_requisition', type_='wizard'
    )