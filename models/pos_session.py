from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = 'pos.session'

    z_report_ids = fields.One2many(
        'pos.session.z.report',
        'session_id',
        string='Reportes Z',
    )
    z_report_count = fields.Integer(
        string='N.º de Reportes Z',
        compute='_compute_z_report_count',
    )
    z_report_emitido = fields.Boolean(
        string='Reporte Z emitido',
        compute='_compute_z_report_emitido',
        store=True,
        help='Indica que la sesión ya tiene su Reporte Z fiscal emitido, por lo '
             'que queda cerrada fiscalmente y no admite nuevas ventas.',
    )

    @api.depends('z_report_ids')
    def _compute_z_report_count(self):
        for session in self:
            session.z_report_count = len(session.z_report_ids)

    @api.depends('z_report_ids.state')
    def _compute_z_report_emitido(self):
        for session in self:
            session.z_report_emitido = any(
                report.state == 'issued' for report in session.z_report_ids
            )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """ Expone el cierre fiscal de la sesión a la interfaz del POS. """
        res = super()._load_pos_data_fields(config_id)
        res.append('z_report_emitido')
        return res

    # ------------------------------------------------------------------
    # Alerta inteligente al cierre de sesión (REQ 2)
    # ------------------------------------------------------------------
    def _kaplan_get_emitted_orders(self):
        """ Pedidos efectivamente emitidos en la sesión.

        Se consideran ventas/facturas emitidas los pedidos pagados, registrados
        en contabilidad o facturados; los borradores y los cancelados no cuentan.
        """
        self.ensure_one()
        return self.get_session_orders().filtered(
            lambda o: o.state in ('paid', 'done', 'invoiced')
        )

    def kaplan_get_z_report_close_info(self):
        """ Estado fiscal de la sesión para decidir la alerta de cierre. """
        self.ensure_one()
        orders = self._kaplan_get_emitted_orders()
        return {
            'session_name': self.display_name,
            'tiene_reporte_z': self.z_report_emitido,
            'tiene_ventas': bool(orders),
            'order_count': len(orders),
            'total_amount': sum(orders.mapped('amount_total')),
            # Con ventas emitidas y sin corte, el Reporte Z es obligatorio para cerrar.
            'requiere_reporte_z': bool(orders) and not self.z_report_emitido,
        }

    def kaplan_generate_z_report(self):
        """ Emite el Reporte Z de la sesión y captura el resumen fiscal. """
        for session in self:
            if session.z_report_emitido:
                raise UserError(_(
                    'La sesión «%s» ya tiene un Reporte Z emitido.',
                    session.display_name,
                ))
            orders = session._kaplan_get_emitted_orders()
            z_report = self.env['pos.session.z.report'].create({
                'session_id': session.id,
                'name': _('Reporte Z %s', session.name or session.display_name),
                'state': 'issued',
                'date': session.stop_at or fields.Datetime.now(),
                'order_count': len(orders),
                'total_amount': sum(orders.mapped('amount_total')),
            })
            session._kaplan_emit_z_report_printax(z_report)
            session.message_post(body=_('Reporte Z emitido: %s', z_report.name))
        return True

    def _kaplan_emit_z_report_printax(self, z_report):
        """ Gancho de la impresora fiscal (Printax).

        Aquí se enviará la orden de corte Z al equipo fiscal y se completarán
        ``name``, ``counter_x``, ``counter_z`` y ``printer_serial`` con la
        respuesta de Printax. Mientras la integración no esté implementada, el
        Reporte Z se registra en Odoo con los datos de la sesión.
        """
        return True

    def kaplan_register_close_without_z_report(self):
        """ Constancia en el chatter de un cierre sin corte fiscal. """
        for session in self:
            if not session.z_report_emitido:
                session.message_post(body=_(
                    'Sesión cerrada sin Reporte Z: no hubo ventas emitidas.',
                ))
        return True

    def action_pos_session_closing_control(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        """ No permite cerrar una sesión con ventas emitidas y sin Reporte Z. """
        for session in self:
            emitted_orders = session._kaplan_get_emitted_orders()
            if emitted_orders and not session.z_report_emitido:
                raise UserError(_(
                    'La sesión «%s» tiene %s venta(s) emitida(s) y no tiene Reporte Z. '
                    'Genere el Reporte Z antes de cerrar la sesión.',
                    session.display_name,
                    len(emitted_orders),
                ))
        return super().action_pos_session_closing_control(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )
