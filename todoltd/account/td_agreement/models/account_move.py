from logging import getLogger
from odoo import fields, models

_logger = getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    td_agreement_id = fields.Many2one(
        string="Agreement",
        comodel_name="td.agreement",
        ondelete="restrict",
    )

    def _post(self, soft=True):
        # Post entries.
        posted = super()._post(soft)
        for move in posted:
            wrong_lines = move.line_ids.filtered(
                lambda x: x.td_agreement_id != move.td_agreement_id
            )
            wrong_lines.write({"td_agreement_id": move.td_agreement_id.id})


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    td_agreement_id = fields.Many2one(
        string="Agreement",
        comodel_name="td.agreement",
        ondelete="restrict",
        tracking=True,
    )
