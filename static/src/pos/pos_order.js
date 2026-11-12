import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    
    set_partner(partner) {
        super.set_partner(...arguments);
        this.set_to_invoice(!!partner);
    },
});
