from odoo import _, models
from odoo.exceptions import UserError

class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    
    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        try:
            res = super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        except Exception as e:
            raise UserError(_("An error occurred while generating the report: %s") % str(e))

        return res