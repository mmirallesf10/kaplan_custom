from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_product_catalog_order_data(self, products, **kwargs):
        """Agrega el precio total con impuestos incluidos a cada producto del catálogo."""
        res = super()._get_product_catalog_order_data(products, **kwargs)
        company = self.company_id or self.env.company
        for product in products:
            if product.id not in res:
                continue
            taxes = product.taxes_id.filtered(
                lambda t: not t.company_id or t.company_id == company
            )
            price_unit = res[product.id].get('price', product.list_price)
            if taxes:
                tax_res = taxes.compute_all(
                    price_unit,
                    currency=self.currency_id or company.currency_id,
                    quantity=1.0,
                    product=product,
                    partner=self.partner_id,
                )
                res[product.id]['price_total'] = tax_res['total_included']
            else:
                res[product.id]['price_total'] = price_unit
        return res