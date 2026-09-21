# -*- coding: utf-8 -*-
from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _get_default_pdf_report_id(self, move):
        """
        Use the custom invoice act report instead of the standard Odoo invoice
        when generating / sending the PDF of a customer invoice.
        A template explicitly set on the partner still takes precedence.
        """
        partner_report = move.commercial_partner_id.with_company(
            move.company_id).invoice_template_pdf_report_id
        if move.move_type == 'out_invoice' and not partner_report:
            # The act report is built from the linked sale order, fall back to
            # the standard invoice when the move has no sale order.
            act_report = self.env.ref(
                'td_medicus_report.action_report_invoice_act',
                raise_if_not_found=False,
            )
            if act_report and move.td_order_id:
                return act_report
        return super()._get_default_pdf_report_id(move)
