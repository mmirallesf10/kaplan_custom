/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ProductCatalogOrderLine } from "@product/product_catalog/order_line/order_line";
import { ProductCatalogKanbanRecord } from "@product/product_catalog/kanban_record";
import { formatMonetary } from "@web/views/fields/formatters";

ProductCatalogOrderLine.props = {
    ...ProductCatalogOrderLine.props,
    price_total: { type: Number, optional: true },
};

patch(ProductCatalogOrderLine.prototype, {
    get priceTotal() {
        const { currencyId, digits } = this.env;
        return formatMonetary(this.props.price_total, { currencyId, digits });
    },

    get showPriceTotal() {
        // Se muestra siempre que el servidor envíe el dato. Con impuestos configurados como
        // "incluidos en el precio" el total coincide con el precio unitario, igual que en la
        // ficha del producto, y no por eso debe ocultarse.
        return this.props.price_total !== undefined && this.props.price_total !== null;
    },

    get priceLabel() {
        return _t("Unit price");
    },

    get priceTotalLabel() {
        return _t("Total price");
    },
});

patch(ProductCatalogKanbanRecord.prototype, {
    get orderLineComponent() {
        const Component = super.orderLineComponent;
        // Las subclases (p. ej. ProductCatalogSaleOrderLine, usada para sale.order) copian los
        // props de la clase base al definirse, antes de que este módulo los amplíe. Se declaran
        // aquí para que la validación de props de OWL no rechace price_total.
        if (Component.props && !("price_total" in Component.props)) {
            Component.props = { ...Component.props, price_total: { type: Number, optional: true } };
        }
        return Component;
    },

    async _updateQuantity() {
        // /product/catalog/update_order_line_info solo devuelve el precio unitario; se mantiene
        // el precio total coherente aplicándole la misma relación impuesto/precio inicial.
        const catalogData = this.productCatalogData;
        const hasPriceTotal = catalogData.price_total !== undefined && catalogData.price_total !== null;
        const taxRatio = hasPriceTotal && catalogData.price ? catalogData.price_total / catalogData.price : null;
        await super._updateQuantity();
        if (taxRatio !== null && catalogData.price) {
            catalogData.price_total = catalogData.price * taxRatio;
        }
    },
});
