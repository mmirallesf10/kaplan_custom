from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_product_catalog_lines_data(self, **kwargs):
        """Agrega el precio con impuestos incluidos a los productos ya presentes en el pedido.

        Los productos que aún no están en la orden pasan por
        ``sale.order._get_product_catalog_order_data``; estos por aquí, así el catálogo
        muestra siempre el mismo dato.
        """
        res = super()._get_product_catalog_lines_data(**kwargs)
        if self and 'price' in res:
            price_total = self[0].order_id._get_product_catalog_price_total(self.product_id, res['price'])
            if price_total is not None:
                res['price_total'] = price_total
        return res
