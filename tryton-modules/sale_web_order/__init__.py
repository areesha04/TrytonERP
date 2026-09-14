from trytond.pool import Pool
from . import sale  
def register():
    # Register all ModelSQL / ModelView classes here
    Pool.register(
        sale.WebOrder,
        sale.WebOrderLine,
        module='sale_web_order', type_='model'
    )