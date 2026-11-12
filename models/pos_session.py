from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = 'pos.session'

    z_report_id = fields.Many2one(
        'account.report.z',
        string='Reporte Z',
        readonly=True,
        copy=False,
        help='Reporte Z (account.report.z de save_z_report) emitido al cerrar '
             'fiscalmente esta sesión de caja.',
    )
    z_report_emitido = fields.Boolean(
        string='Reporte Z emitido',
        compute='_compute_z_report_emitido',
        store=True,
        help='Indica que la sesión ya tiene su Reporte Z fiscal emitido, por lo '
             'que queda cerrada fiscalmente y no admite nuevas ventas.',
    )

    @api.depends('z_report_id', 'z_report_id.state')
    def _compute_z_report_emitido(self):
        for session in self:
            session.z_report_emitido = bool(
                session.z_report_id and session.z_report_id.state == 'close'
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
        error_orders = orders.filtered('kaplan_fiscal_error')
        return {
            'session_name': self.display_name,
            'tiene_reporte_z': self.z_report_emitido,
            'tiene_ventas': bool(orders),
            'order_count': len(orders),
            'total_amount': sum(orders.mapped('amount_total')),
            # Con ventas emitidas y sin corte, el Reporte Z es obligatorio para cerrar.
            'requiere_reporte_z': bool(orders) and not self.z_report_emitido,
            # Pedidos con Error Fiscal bloquean el cierre hasta resolverse.
            'tiene_error_fiscal': bool(error_orders),
            'error_fiscal_count': len(error_orders),
        }

    def _kaplan_ensure_open_z_report(self, journal):
        """ Devuelve el ``account.report.z`` vigente del diario.

        Si el reporte del número actual está cerrado (el número del diario no
        avanzó, por ejemplo porque ``action_close`` falló en silencio al no
        tener impresora fiscal configurada), se incrementa el número y se
        crea/recupera el siguiente reporte en borrador. Así cada sesión obtiene
        un reporte Z distinto y las facturas nunca se adhieren a uno cerrado.
        """
        ReportZ = self.env['account.report.z'].sudo()
        number = journal.x_account_z_report_number
        while True:
            z_report = ReportZ.search([
                ('journal_id', '=', journal.id),
                ('name', '=', number),
                ('company_id', '=', journal.company_id.id),
            ], limit=1)
            if z_report and z_report.state != 'close':
                return z_report

            # Número vacío o reporte ya cerrado: avanzar al siguiente.
            number = (
                ReportZ._increment_char(number) if number else '0001'
            )
            journal.x_account_z_report_number = number
            z_report = ReportZ.search([
                ('journal_id', '=', journal.id),
                ('name', '=', number),
                ('company_id', '=', journal.company_id.id),
            ], limit=1)
            if not z_report:
                return ReportZ.create({
                    'name': number,
                    'journal_id': journal.id,
                    'x_fiscal_printer_id': journal.x_fiscal_printer_id.id,
                    'company_id': journal.company_id.id,
                    'state': 'draft',
                })

    def kaplan_generate_z_report(self):
        """ Emite el Reporte Z de la sesión usando ``account.report.z``.

        El reporte Z de ``save_z_report`` es por diario de ventas: se toma el
        ``account.report.z`` vigente del diario de facturación del POS
        (``invoice_journal_id``), se abre si está en borrador y se cierra con
        ``action_close()``, lo que incrementa la secuencia del diario y deja
        las facturas siguientes adheridas al siguiente reporte.
        """
        for session in self:
            if session.z_report_emitido:
                raise UserError(_(
                    'La sesión «%s» ya tiene un Reporte Z emitido.',
                    session.display_name,
                ))
            journal = session.config_id.invoice_journal_id or session.config_id.journal_id
            if not journal:
                raise UserError(_(
                    'La sesión «%s» no tiene un diario de ventas configurado '
                    'en su punto de venta.',
                    session.display_name,
                ))
            z_report = session._kaplan_ensure_open_z_report(journal)
            if z_report.state == 'draft':
                z_report.action_open()
            # Adhiere las facturas de la sesión al reporte. Es necesario porque
            # account.move.report_z_id es un compute almacenado que se resolvió
            # al publicar la factura; si el reporte aún no existía, quedó vacío
            # y no se recalcula solo. Solo se tocan las que no tienen reporte.
            session_moves = session.order_ids.account_move.filtered(
                lambda m: m.state == 'posted'
                and m.move_type in ('out_invoice', 'out_refund')
                and not m.report_z_id
            )
            if session_moves:
                session_moves.write({'report_z_id': z_report.id})
            if z_report.state == 'open':
                z_report.action_close()
            # action_close() no incrementa el número del diario si falta la
            # impresora fiscal o el número (falla en silencio). En ese caso se
            # avanza manualmente para que el próximo reporte sea distinto.
            if journal.x_account_z_report_number == z_report.name:
                journal.x_account_z_report_number = (
                    self.env['account.report.z']._increment_char(z_report.name)
                )
            session.z_report_id = z_report.id
            session.message_post(body=_(
                'Reporte Z emitido: %s', z_report.display_name,
            ))
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
            error_orders = emitted_orders.filtered('kaplan_fiscal_error')
            if error_orders:
                raise UserError(_(
                    'La sesión «%s» tiene %s pedido(s) con Error Fiscal / Revisión '
                    'Manual. Resuelva las incidencias fiscales antes de cerrar '
                    'la sesión.',
                    session.display_name,
                    len(error_orders),
                ))
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
