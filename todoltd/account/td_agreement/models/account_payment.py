import json
from odoo import api, fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    td_agreement_id = fields.Many2one(
        string="Agreement",
        comodel_name="td.agreement",
        ondelete="restrict",
        tracking=True,
    )

    td_agreement_id_domain = fields.Char(
        compute="_compute_agreement_id_domain", readonly=True, store=False
    )

    @api.depends("partner_id")
    def _compute_agreement_id_domain(self):
        for rec in self:
            filter_ids = rec.partner_id.mapped("id") + rec.partner_id.mapped(
                "child_ids.id"
            )
            rec.td_agreement_id_domain = json.dumps([("partner_id", "in", filter_ids)])

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        for pay in payments:
            pay.move_id.write({"td_agreement_id": pay.td_agreement_id.id})
        return payments

    def write(self, vals):
        res = super().write(vals)
        changed_fields = set(vals.keys())
        if any(field_name in changed_fields for field_name in ("", "td_agreement_id")):
            for pay in self.with_context(skip_account_move_synchronization=True):
                pay.move_id.with_context(skip_invoice_sync=True).write(
                    {
                        "td_agreement_id": pay.td_agreement_id.id,
                    }
                )
        return res
