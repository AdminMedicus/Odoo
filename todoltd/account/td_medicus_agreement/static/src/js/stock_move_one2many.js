/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { MovesListRenderer } from "@stock/views/picking_form/stock_move_one2many";

/**
 * Stock appends the "open detailed operations" (stock.move.line) button as the
 * very last column of the moves list. Medicus wants that button right after the
 * Product column, so the user does not have to scroll to the end of a wide list.
 */
patch(MovesListRenderer.prototype, {
    processAllColumn(allColumns, list) {
        const columns = super.processAllColumn(...arguments);
        if (list.resModel !== "stock.move") {
            return columns;
        }
        const detailsIndex = columns.findIndex((col) => col.type === "opendetailsop");
        const productIndex = columns.findIndex(
            (col) => col.type === "field" && col.name === "product_id"
        );
        if (detailsIndex === -1 || productIndex === -1 || detailsIndex <= productIndex) {
            return columns;
        }
        const [detailsColumn] = columns.splice(detailsIndex, 1);
        columns.splice(productIndex + 1, 0, detailsColumn);
        return columns;
    },
});
