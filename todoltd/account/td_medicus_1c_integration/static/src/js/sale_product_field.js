/* @odoo-module */

import { patch } from "@web/core/utils/patch";
import { saleOrderLineProductField } from "@sale/js/sale_product_field";
import {
    productLabelSectionAndNoteField,
} from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";

patch(saleOrderLineProductField, {
    extractProps(fieldInfo, dynamicInfo) {
        const props = productLabelSectionAndNoteField.extractProps(...arguments);
        props.readonlyField = dynamicInfo.readonly;
        props.canCreate = false
        props.canCreateEdit = false
        props.canQuickCreate = false
        props.canOpen = false
        return props;
    },
})