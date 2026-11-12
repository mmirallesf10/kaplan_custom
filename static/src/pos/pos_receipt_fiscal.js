/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup();
        onMounted(() => this.kaplanAutoPrintFiscal());
    },

    kaplanAutoPrintFiscal() {
        try {
            const order = this.currentOrder;
            console.info("[Kaplan] kaplanAutoPrintFiscal", {
                autoPrint: this.pos.config.printax_auto_print,
                orderId: order && order.id,
                finalized: order && order.finalized,
                hasButton: typeof this.OnClickFacturaFiscal === "function",
            });
            if (
                !this.pos.config.printax_auto_print ||
                !order ||
                !order.finalized ||
                typeof order.id !== "number" ||
                typeof this.OnClickFacturaFiscal !== "function" ||
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
