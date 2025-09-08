from odoo import fields, models


class TdAgreementClosingWizard(models.TransientModel):
    _name = "td.agreement.closing.wizard"
    _description = "Closing Agreement Wizard"

    agreement_id = fields.Many2one(
        comodel_name="td.agreement",
        required=True)
    closing_reason_id = fields.Many2one(
        comodel_name="td.agreement.closing.reason",
        string="Closing Reason"
    )
    notes = fields.Text(string="Notes")

    def action_close(self):
        agreement = self.agreement_id

        agreement.is_closed = True
        agreement.closing_reason_id = self.closing_reason_id
        return {
            "type": "ir.actions.act_window",
            "name": "Agreements",
            "res_model": "td.agreement",
            "view_mode": "form",
            "view_id": self.env.ref("td_agreement.td_agreement_form").id,
            "res_id": agreement.id,
            "target": "current",
        }

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
