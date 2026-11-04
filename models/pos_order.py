from odoo import api, models, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    @api.model_create_multi
    def create(self, vals_list):
        """ Impide crear pedidos en una sesión que ya tiene Reporte Z emitido.

        La sesión queda cerrada fiscalmente al emitirse el Reporte Z, por lo que no
        se admiten ventas nuevas desde el backend ni desde otras automatizaciones.

        La sincronización diferida de la interfaz del POS (ventas generadas sin
        conexión antes del corte) se exime mediante el contexto
        ``kaplan_pos_sync_from_ui``: esas ventas sí se registran para que queden
        auditables, en lugar de abortar el lote completo de sincronización.
        """
        if not self.env.context.get('kaplan_pos_sync_from_ui'):
            session_ids = {vals.get('session_id') for vals in vals_list if vals.get('session_id')}
            blocked = self.env['pos.session'].browse(session_ids).filtered('z_report_emitido')
            if blocked:
                raise UserError(_(
                    'La sesión de caja «%s» ya tiene Reporte Z emitido, por lo que está '
                    'cerrada fiscalmente y no admite nuevas ventas.',
                    blocked[0].display_name,
                ))
        return super().create(vals_list)

    def sync_from_ui(self, orders):
        """ Marca la sincronización de la interfaz para eximirla del bloqueo. """
        return super(PosOrder, self.with_context(kaplan_pos_sync_from_ui=True)).sync_from_ui(orders)
