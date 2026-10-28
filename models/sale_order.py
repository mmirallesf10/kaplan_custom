from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_product_catalog_price_total(self, product, price_unit):
        """Devuelve el precio unitario con los impuestos de venta incluidos.

        Reproduce el cálculo con el que la ficha del producto muestra el importe
        («Incl. Taxes» en `account.product._construct_tax_string`): impuestos de venta
        del producto filtrados por la compañía del pedido y mapeados por la posición
        fiscal. Devuelve ``None`` si el producto no aplica impuestos de venta, para no
        mostrar en el catálogo un precio duplicado e inútil.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        taxes = product.taxes_id._filter_taxes_by_company(company)
        if not taxes:
            return None
        fiscal_position = self.fiscal_position_id
        if not fiscal_position:
            fiscal_position = self.env['account.fiscal.position'].with_company(company)._get_fiscal_position(
                self.partner_id, self.partner_shipping_id,
            )
        taxes = fiscal_position.map_tax(taxes)
        total_included = taxes.compute_all(
            price_unit,
            currency=currency,
            quantity=1.0,
            product=product,
            partner=self.partner_id,
        )['total_included']
        return currency.round(total_included)

    def _get_product_catalog_order_data(self, products, **kwargs):
        """Agrega el precio total con impuestos incluidos a cada producto del catálogo."""
        res = super()._get_product_catalog_order_data(products, **kwargs)
        for product in products:
            product_data = res.get(product.id)
            if product_data is None or 'price' not in product_data:
                continue
            price_total = self._get_product_catalog_price_total(product, product_data['price'])
            if price_total is not None:
                product_data['price_total'] = price_total
        return res
