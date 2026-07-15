from trytond.pool import Pool
from .shipment import BulkAddShipmentLine, BulkAddShipment, ShipmentInternal, BulkAddShipmentStart,BulkAddShipmentStartProduct

def register():
    Pool.register(
        ShipmentInternal,  
        BulkAddShipmentStart,  
        BulkAddShipmentStartProduct,
        BulkAddShipmentLine,
        module='custom_stock', type_='model'
    )
    Pool.register(
        BulkAddShipment,
        module='custom_stock', type_='wizard'
    )