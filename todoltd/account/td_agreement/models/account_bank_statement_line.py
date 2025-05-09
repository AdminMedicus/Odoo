from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    td_agreement_id = fields.Many2one(
        string="Agreement",
        comodel_name="td.agreement",
        ondelete="restrict",
        compute="_compute_td_agreement_id",
    )

    def _compute_td_agreement_id(self):
        for rec in self:
            rec.td_agreement_id = rec.move_id.td_agreement_id
