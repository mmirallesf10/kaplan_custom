/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductCatalogOrderLine } from "@product/product_catalog/order_line/order_line";
import { formatMonetary } from "@web/views/fields/formatters";

ProductCatalogOrderLine.props = {
    ...ProductCatalogOrderLine.props,
    price_total: { type: Number, optional: true },
};

patch(ProductCatalogOrderLine.prototype, {
    get priceTotal() {
        const { currencyId, digits } = this.env;
        const value = this.props.price_total ?? this.props.price;
        return formatMonetary(value, { currencyId, digits });
    },

    get showPriceTotal() {
        return (
            this.props.price_total !== undefined &&
            this.props.price_total !== null &&
            this.props.price_total !== this.props.price
        );
    },
});