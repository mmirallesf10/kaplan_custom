from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    price_total_with_tax = fields.Float(
        string="Precio total (impuestos incluidos)",
        compute='_compute_price_total_with_tax',
        digits='Product Price',
    )

    @api.depends('list_price', 'taxes_id')
    def _compute_price_total_with_tax(self):
        for product in self:
            taxes = product.taxes_id.filtered(lambda t: t.company_id == self.env.company) or product.taxes_id
            if taxes:
                res = taxes.compute_all(
                    product.list_price,
                    currency=self.env.company.currency_id,
                    quantity=1.0,
                    product=product,
                    partner=False,
                )
                product.price_total_with_tax = res['total_included']
            else:
                product.price_total_with_tax = product.list_price