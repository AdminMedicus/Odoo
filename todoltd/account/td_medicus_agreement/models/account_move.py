from odoo import models, api, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _description = "Account Move"
    _inherit = "account.move"

    @api.onchange('partner_id')
    def _compute_td_agreement_id(self):
        for account in self:
            if account.partner_id:
                main_contract = self.env['td.agreement'].search([
                    ('partner_id', '=', account.partner_id.id),
                    ('main_contract', '=', True)
                ], limit=1)
                if main_contract:
                    account.td_agreement_id = main_contract.id
                else:
                    account.td_agreement_id = False
            else:
                account.td_agreement_id = False

    def action_post(self):
        res = super(AccountMove, self).action_post()

        agreement = self.td_agreement_id
        if agreement.contract_amount != 0:
            td_account_move_count = 0.0
            for account_move in agreement.account_move_ids:
                if (account_move.move_type == 'out_invoice'
                        and account_move.state == 'posted'):
                    td_account_move_count += (
                        account_move.amount_total_in_currency_signed)

            if td_account_move_count > agreement.contract_amount:
                raise ValidationError(_("The amount specified in the contract "
                                        "is less than the total amount of "
                                        "the document"))
        return res
