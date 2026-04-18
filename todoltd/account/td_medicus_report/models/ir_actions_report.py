from odoo import _, api, fields, models
from odoo.exceptions import UserError


REPORT_IDS = [
    'td_medicus_report.report_wholesale_invoice',
    'td_medicus_report.report_wholesale_picking',
    'td_medicus_report.report_print_custody_transfer_act',
    'td_medicus_report.report_print_custody_return_act',
]

class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        try:
            res = super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        except Exception as e:
            raise UserError(_("An error occurred while generating the report: %s") % str(e))

        return res