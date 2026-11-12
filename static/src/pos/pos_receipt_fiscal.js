/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onMounted, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { SendToPrintax } from "@printax_pos_18/js/printax";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup();
        this.rpc = this.rpc || useService("orm");
        this.kaplanFiscalState = useState({ printed: false, printing: false });
        onMounted(() => this.kaplanInitFiscalGuard());
    },

    async kaplanInitFiscalGuard() {
        await this.kaplanCheckFiscalPrinted();
        if (this.pos.config.printax_auto_print) {
            this.kaplanAutoPrintFiscal();
        }
    },

    async kaplanCheckFiscalPrinted() {
        const order = this.currentOrder;
        if (!order || typeof order.id !== "number") {
            return false;
        }
        if (sessionStorage.getItem("LastInvoice") == order.id) {
            this.kaplanFiscalState.printed = true;
            return true;
        }
        try {
            const [data] = await this.rpc.read("pos.order", [order.id], [
                "ptx_fiscal_invoice",
                "ptx_fiscal_refund",
            ]);
            if (data && (data.ptx_fiscal_invoice || data.ptx_fiscal_refund)) {
                this.kaplanFiscalState.printed = true;
                return true;
            }
        } catch (error) {
            console.error("Kaplan fiscal status check error:", error);
        }
        return false;
    },

    async kaplanCheckPrinter() {
        try {
            return await this.rpc.call("pos.config", "kaplan_printax_check", [
                this.pos.config.id,
            ]);
        } catch (error) {
            console.error("Kaplan printer check error:", error);
            return { ok: false, error: "No se pudo verificar la impresora fiscal" };
        }
    },

    async kaplanMarkFiscalError(orderId, message) {
        try {
            await this.rpc.call("pos.order", "kaplan_mark_fiscal_error", [
                orderId,
                message || "",
            ]);
        } catch (error) {
            console.error("Kaplan mark fiscal error failed:", error);
        }
    },

    async OnClickFacturaFiscal(...args) {
        // Spinner activo: se ignoran clicks adicionales hasta la respuesta.
        if (this.kaplanFiscalState.printing) {
            return;
        }
        if (await this.kaplanCheckFiscalPrinted()) {
            this.notification.add(
                "Documento fiscal ya ha sido procesado",
                {
                    title: "PrinTax",
                    type: "warning",
                    sticky: false,
                }
            );
            return;
        }

        const orderId = this.currentOrder && this.currentOrder.id;
        if (typeof orderId !== "number") {
            return;
        }

        this.kaplanFiscalState.printing = true;
        try {
            // Handshake: solo se envía la impresión si PrinTax responde.
            const check = await this.kaplanCheckPrinter();
            if (!check || !check.ok) {
                await this.kaplanMarkFiscalError(
                    orderId,
                    "Impresora fiscal no disponible"
                );
                this.notification.add(
                    "Impresora fiscal no disponible. El pedido quedó marcado con Error Fiscal.",
                    {
                        title: "PrinTax",
                        type: "danger",
                        sticky: true,
                    }
                );
                return;
            }

            const respuesta = await this.rpc.call(
                "pos.order",
                "printax_print_invoice",
                [0, orderId]
            );

            if (respuesta.tip == "ERR") {
                this.notification.add(respuesta.err, {
                    title: "PrinTax",
                    type: "danger",
                    sticky: false,
                });
                return;
            }

            const endpoint =
                (this.currentOrder.config_id &&
                    this.currentOrder.config_id.printax_endpoint) ||
                this.pos.config.printax_endpoint;

            // Se espera la respuesta real de la impresora (~5s): el spinner
            // permanece hasta que llega el COK/ERR del dispositivo.
            const xhr = await SendToPrintax(endpoint, respuesta.msg, () => {});

            if (xhr.status != 200) {
                await this.kaplanMarkFiscalError(
                    orderId,
                    `Error de comunicación con PrinTax (${xhr.status})`
                );
                this.notification.add(xhr.statusText || "Petición de impresión fallida", {
                    title: "PrinTax",
                    type: "danger",
                    sticky: false,
                });
                return;
            }

            let resp;
            try {
                resp = JSON.parse(xhr.responseText);
            } catch (error) {
                await this.kaplanMarkFiscalError(
                    orderId,
                    "Respuesta inválida de la impresora fiscal"
                );
                this.notification.add("Respuesta inválida de la impresora fiscal", {
                    title: "PrinTax",
                    type: "danger",
                    sticky: true,
                });
                return;
            }

            if (resp.TIP == "COK") {
                await this.rpc.call("pos.order", "update_invoice", [
                    0,
                    respuesta.ord,
                    resp.FAC,
                    resp.NCR,
                    resp.SER,
                    resp.FEC,
                    resp.VTA,
                    resp.IVA,
                    resp.RPZ,
                ]);

                sessionStorage.setItem("LastInvoice", orderId);
                this.kaplanFiscalState.printed = true;

                this.notification.add(
                    "El documento fiscal fue procesado correctamente",
                    {
                        title: "PrinTax",
                        type: "success",
                        sticky: false,
                    }
                );
            } else {
                const errMsg = resp.ERR || "La impresora fiscal rechazó el documento";
                await this.kaplanMarkFiscalError(orderId, errMsg);
                this.notification.add(errMsg, {
                    title: "PrinTax",
                    type: "danger",
                    sticky: true,
                });
            }
        } catch (error) {
            console.error("Kaplan fiscal print error:", error);
            await this.kaplanMarkFiscalError(
                orderId,
                "Error al enviar el documento fiscal"
            );
            this.notification.add("Error al enviar el documento fiscal", {
                title: "PrinTax",
                type: "danger",
                sticky: true,
            });
        } finally {
            this.kaplanFiscalState.printing = false;
        }
    },

    kaplanAutoPrintFiscal() {
        try {
            const order = this.currentOrder;
            if (
                !this.pos.config.printax_auto_print ||
                !order ||
                !order.finalized ||
                typeof order.id !== "number" ||
                typeof this.OnClickFacturaFiscal !== "function" ||
                this.kaplanFiscalState.printed ||
                this.kaplanFiscalState.printing ||
                sessionStorage.getItem(`KaplanFiscalAuto_${order.id}`)
            ) {
                return;
            }

            sessionStorage.setItem(`KaplanFiscalAuto_${order.id}`, "1");
            this.OnClickFacturaFiscal();
        } catch (error) {
            console.error("Kaplan auto fiscal print error:", error);
        }
    },
});
