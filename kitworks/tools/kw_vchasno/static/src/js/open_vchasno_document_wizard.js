/** @odoo-module **/

import { registry } from "@web/core/registry";  // eslint-disable-line
import { useService } from "@web/core/utils/hooks";  // eslint-disable-line
import { listView } from "@web/views/list/list_view";  // eslint-disable-line
import { patch } from "@web/core/utils/patch";  // eslint-disable-line

const {useComponent } = owl;

export function VchasnoDocumentCreateButton() {
    const component = useComponent();
    const action = useService("action");

    component.onClickCreateDocumentVchasno = () => {
        action.doAction({
            type: "ir.actions.act_window",
            res_model: "vchasno.download.document.wizard",
            name: "Add Document",
            view_mode: "form",
            view_type: "form",
            views: [[false, "form"]],
            target: "new",
        });
    };
}

export const VchasnoListView = {
    ...listView,
};

registry.category("views").add("kw_vchasno_kw_vchasno_document_list", VchasnoListView);

patch(VchasnoListView.Controller.prototype, {
    setup() {
        super.setup(...arguments);
        VchasnoDocumentCreateButton();
    },
});
