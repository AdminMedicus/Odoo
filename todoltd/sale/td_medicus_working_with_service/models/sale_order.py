from odoo import api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.project_id and record.project_id.is_fsm:
                record.implementation_document = 'exp_inv'
            if 'fsm_task_id' in self.env.context:
                task_id = self.env.context.get('fsm_task_id')
                task = self.env['project.task'].browse(task_id)
                record.td_agreement_id = task.td_agreement_id.id if task.td_agreement_id else False
        return records

    def write(self, vals):
        if 'state' in vals and vals['state'] == 'sale':
            if 'validate_analytic' not in self.env.context:
                vals['state'] = self.state
        res = super().write(vals)
        return res
