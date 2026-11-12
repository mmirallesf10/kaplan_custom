from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = 'pos.order'

    kaplan_fiscal_error = fields.Boolean(
        string='Error Fiscal',
        copy=False,
        help='La impresora fiscal no confirmó el documento de esta orden. '
             'Bloquea el cierre de sesión hasta resolverse.',
    )
    kaplan_fiscal_error_msg = fields.Char(
        string='Detalle del Error Fiscal',
        copy=False,
    )
    kaplan_fiscal_error_date = fields.Datetime(
        string='Fecha del Error Fiscal',
        copy=False,
    )

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

    @api.model
    def sync_from_ui(self, orders):
        """ Marca la sincronización de la interfaz para eximirla del bloqueo. """
        return super(PosOrder, self.with_context(kaplan_pos_sync_from_ui=True)).sync_from_ui(orders)

    def printax_print_invoice(self, id_order):
        """ Evita duplicar el documento fiscal de una orden.

        ``ptx_fiscal_invoice`` / ``ptx_fiscal_refund`` solo se llenan cuando la
        impresora fiscal responde ``COK`` (``update_invoice``), por lo que su
        presencia garantiza que el proceso fue exitoso. Se devuelve el formato
        ``ERR`` que espera el POS para mostrar la notificación de PrinTax en
        lugar del ``UserError`` genérico de ``armar_comando``.
        """
        order = self.browse(id_order)
        if order.exists() and (order.ptx_fiscal_invoice or order.ptx_fiscal_refund):
            return {
                'tip': 'ERR',
                'err': _('El documento fiscal ya fue procesado para esta orden.'),
                'ord': id_order,
            }
        return super().printax_print_invoice(id_order)

    # ------------------------------------------------------------------
    # Incidencias de impresión fiscal (REQ 6) y mapeo a factura contable (REQ 7)
    # ------------------------------------------------------------------
    def kaplan_mark_fiscal_error(self, message=False):
        """ Marca la orden con Error Fiscal / Revisión Manual."""
        for order in self:
            order.write({
                'kaplan_fiscal_error': True,
                'kaplan_fiscal_error_msg': message or _('Sin confirmación de la impresora fiscal'),
                'kaplan_fiscal_error_date': fields.Datetime.now(),
            })
            order.message_post(body=_(
                'Error Fiscal: %s', order.kaplan_fiscal_error_msg,
            ))
        return True

    def kaplan_resolve_fiscal_error(self):
        """ Resolución manual de la incidencia por un supervisor."""
        for order in self:
            if not order.kaplan_fiscal_error:
                continue
            order.write({
                'kaplan_fiscal_error': False,
                'kaplan_fiscal_error_msg': False,
                'kaplan_fiscal_error_date': False,
            })
            order.message_post(body=_(
                'Error Fiscal resuelto manualmente por %s.', self.env.user.display_name,
            ))
        return True

    def _kaplan_sync_fiscal_to_invoice(self):
        """ Traspasa los datos de PrinTax del pos.order a la factura contable.

        El número de la factura fiscal (o de la nota de crédito fiscal) se
        asigna tal cual al Número de Control (``inv_control_number``) de la
        factura contable, ya que ``save_pos_account`` desactiva la secuencia
        automática para documentos POS.
        """
        self.ensure_one()
        move = self.account_move
        if not move:
            return
        vals = {}
        field_map = {
            'ptx_fiscal_invoice': self.ptx_fiscal_invoice or False,
            'ptx_fiscal_refund': self.ptx_fiscal_refund or False,
            'ptx_serial_printer': self.ptx_serial_printer or False,
            'ptx_printed_date': self.ptx_printed_date or False,
            'ptx_base_imponible': self.ptx_base_imponible or 0.0,
            'ptx_impuesto_printer': self.ptx_impuesto_printer or 0.0,
            'ptx_reporte_z': self.ptx_reporte_z or False,
        }
        for fname, value in field_map.items():
            if fname in move._fields:
                vals[fname] = value
        fiscal_number = (
            self.ptx_fiscal_refund if self.refunded_order_id else self.ptx_fiscal_invoice
        )
        if (
            fiscal_number
            and 'inv_control_number' in move._fields
            and not move.inv_control_number
        ):
            vals['inv_control_number'] = fiscal_number
        if vals:
            move.write(vals)

    def _kaplan_clear_fiscal_error(self):
        """ Limpia la incidencia fiscal tras una impresión exitosa. """
        for order in self.filtered('kaplan_fiscal_error'):
            order.write({
                'kaplan_fiscal_error': False,
                'kaplan_fiscal_error_msg': False,
                'kaplan_fiscal_error_date': False,
            })

    def update_invoice(self, id_order, strFac, strNcr, strSer, strFec, strVta, strIva, strRpz):
        res = super().update_invoice(id_order, strFac, strNcr, strSer, strFec, strVta, strIva, strRpz)
        order = self.browse(id_order)
        if order.exists():
            order._kaplan_sync_fiscal_to_invoice()
            order._kaplan_clear_fiscal_error()
        return res

    def update_invoice_if_new(self, rim, id_order, resp):
        res = super().update_invoice_if_new(rim, id_order, resp)
        if not rim:
            order = self.browse(id_order)
            if order.exists():
                order._kaplan_sync_fiscal_to_invoice()
                order._kaplan_clear_fiscal_error()
        return res
