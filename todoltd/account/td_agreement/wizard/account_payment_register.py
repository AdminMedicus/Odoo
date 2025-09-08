from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    def _init_payments(self, to_process, edit_mode=False):
        payments = super()._init_payments(to_process, edit_mode=edit_mode)

        for payment in payments:
            payment.td_agreement_id = self.line_ids[-1].move_id.td_agreement_id
