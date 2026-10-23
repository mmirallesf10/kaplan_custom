from odoo import models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        if 'vat' not in fields:
            fields.append('vat')
        return fields