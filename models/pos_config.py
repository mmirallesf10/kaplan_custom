import requests

from odoo import models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def kaplan_printax_check(self):
        """ Sonda de conexión con PrinTax antes de enviar una impresión.

        PrinTax no documenta un comando de estado; cualquier respuesta HTTP
        del endpoint demuestra que el puente fiscal está activo. Si no hay
        respuesta (timeout/conexión rechazada), la impresión no se envía.
        """
        self.ensure_one()
        try:
            requests.post(self.printax_endpoint, data=b'', timeout=3)
            return {'ok': True}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}
