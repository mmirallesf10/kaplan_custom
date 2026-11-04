import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ask } from "@point_of_sale/app/store/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    // --------------------------------------------------------------------
    // REQ 1: Vinculación y bloqueo por Reporte Z
    // --------------------------------------------------------------------
    /**
     * La sesión está cerrada fiscalmente cuando ya tiene un Reporte Z emitido.
     * El dato se sirve desde el servidor (campo z_report_emitido de pos.session,
     * expuesto en _load_pos_data_fields), por lo que es fiable aunque el POS
     * haya arrancado sin conexión.
     */
    kaplanIsSessionClosedFiscally() {
        return !!(this.session && this.session.z_report_emitido);
    },
    _kaplanShowClosedSessionMessage() {
        // El aviso fuerte se muestra una sola vez; las siguientes intentos
        // reciben solo una notificación para no saturar la pantalla.
        if (this._kaplanClosedSessionAlertShown) {
            this.notification.add(
                _t("La sesión ya tiene Reporte Z emitido: no se admiten ventas nuevas."),
                { type: "warning" }
            );
            return;
        }
        this._kaplanClosedSessionAlertShown = true;
        this.dialog.add(AlertDialog, {
            title: _t("Sesión cerrada fiscalmente"),
            body: _t(
                "Esta sesión ya tiene Reporte Z emitido, por lo que no se pueden registrar " +
                    "ventas nuevas. Cierra la sesión y abre una nueva para seguir vendiendo."
            ),
        });
    },
    async addLineToOrder(vals, order, opts, configure) {
        // addLineToOrder es el único camino por el que pasa toda venta del POS
        // (clic de producto, lector de código, báscula, combos y propinas).
        if (this.kaplanIsSessionClosedFiscally()) {
            this._kaplanShowClosedSessionMessage();
            return undefined;
        }
        return super.addLineToOrder(...arguments);
    },

    // --------------------------------------------------------------------
    // REQ 2: Alerta inteligente al cierre de sesión
    // --------------------------------------------------------------------
    async kaplanGetZReportCloseInfo() {
        // Se consulta al servidor, no al cache del navegador, para decidir con
        // el estado real de las ventas de la sesión.
        return this.data.call("pos.session", "kaplan_get_z_report_close_info", [
            [this.session.id],
        ]);
    },
    async kaplanGenerateZReport() {
        await this.data.call("pos.session", "kaplan_generate_z_report", [[this.session.id]]);
        // Refresca el flag en el store para que el bloqueo (REQ 1) y el banner
        // de la barra superior actúen de inmediato, sin recargar el POS.
        this.session.z_report_emitido = true;
        this.notification.add(_t("Reporte Z emitido satisfactoriamente."), { type: "success" });
    },
    async closeSession() {
        if (!this._kaplanCloseWithoutZReportAccepted) {
            const info = await this.kaplanGetZReportCloseInfo();
            if (!info.tiene_reporte_z) {
                if (info.requiere_reporte_z) {
                    // Hay ventas emitidas: el corte fiscal es obligatorio.
                    const generated = await ask(this.dialog, {
                        title: _t("Falta el Reporte Z"),
                        body: _t(
                            "La sesión %s tiene %d venta(s) emitida(s) por un total de %s y no " +
                                "tiene Reporte Z. Debes generarlo antes de cerrar la sesión.",
                            info.session_name,
                            info.order_count,
                            this.env.utils.formatCurrency(info.total_amount)
                        ),
                        confirmLabel: _t("Generar Reporte Z"),
                        cancelLabel: _t("Cancelar cierre"),
                    });
                    if (!generated) {
                        return;
                    }
                    await this.kaplanGenerateZReport();
                } else {
                    // Sin Reporte Z y sin ventas: dos opciones explícitas.
                    const generate = await ask(this.dialog, {
                        title: _t("Reporte Z de la sesión"),
                        body: _t(
                            "Esta sesión no tiene Reporte Z y no se emitieron ventas en ella. " +
                                "¿Quieres generarlo o cerrar la sesión sin Reporte Z?"
                        ),
                        confirmLabel: _t("Generarlo"),
                        cancelLabel: _t("Cerrar sin Reporte Z"),
                    });
                    if (generate) {
                        await this.kaplanGenerateZReport();
                    } else {
                        // Queda constancia en el chatter de la sesión.
                        this._kaplanCloseWithoutZReportAccepted = true;
                        await this.data.call(
                            "pos.session",
                            "kaplan_register_close_without_z_report",
                            [[this.session.id]]
                        );
                    }
                }
            }
        }
        return super.closeSession(...arguments);
    },
});
