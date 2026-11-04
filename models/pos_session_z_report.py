from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosSessionZReport(models.Model):
    """Reporte Z de la impresora fiscal (Printax) vinculado a una sesión de caja.

    La relación es unívoca: una sesión de caja admite un único Reporte Z. Cuando
    existe uno en estado «Emitido», la sesión queda cerrada fiscalmente y no se
    admiten pedidos nuevos (ver ``pos.order`` en este mismo módulo).
    """
    _name = 'pos.session.z.report'
    _description = 'Reporte Z de sesión POS'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Número de Reporte Z',
        required=True,
        default=lambda self: _('Nuevo'),
        help='Número de Reporte Z asignado por la impresora fiscal (Printax).',
    )
    session_id = fields.Many2one(
        'pos.session',
        string='Sesión de caja',
        required=True,
        ondelete='restrict',
        index=True,
    )
    config_id = fields.Many2one(
        related='session_id.config_id',
        string='Punto de venta',
        store=True,
    )
    company_id = fields.Many2one(
        related='session_id.company_id',
        string='Compañía',
        store=True,
        readonly=False,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Moneda',
    )
    date = fields.Datetime(
        string='Fecha de emisión',
        required=True,
        default=fields.Datetime.now,
    )
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('issued', 'Emitido'),
        ],
        string='Estado',
        required=True,
        index=True,
        default='issued',
        help='Solo un Reporte Z en estado «Emitido» cierra fiscalmente la sesión.',
    )
    # Datos que devuelve la impresora fiscal al emitir el corte
    counter_x = fields.Integer(string='Contador X')
    counter_z = fields.Integer(string='Contador Z')
    printer_serial = fields.Char(string='Serial de la impresora fiscal')
    # Resumen de la sesión capturado en el momento de la emisión
    order_count = fields.Integer(string='N.º de pedidos')
    total_amount = fields.Monetary(
        string='Total emitido',
        currency_field='currency_id',
    )

    _sql_constraints = [
        ('unique_session_z_report', 'unique(session_id)',
         'Esta sesión de caja ya tiene un Reporte Z registrado.'),
    ]

    @api.constrains('session_id')
    def _check_unique_session(self):
        """ Restricción en ORM del vínculo unívoco sesión <-> Reporte Z.

        Complementa al _sql_constraint para dar un mensaje claro en formularios
        y datos importados, sin depender del error de base de datos.
        """
        for report in self:
            if not report.session_id:
                continue
            duplicates = self.search_count([
                ('session_id', '=', report.session_id.id),
                ('id', '!=', report.id),
            ])
            if duplicates:
                raise ValidationError(_(
                    'La sesión de caja «%s» solo puede tener un Reporte Z.',
                    report.session_id.display_name,
                ))
