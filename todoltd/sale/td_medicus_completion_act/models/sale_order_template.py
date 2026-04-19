from odoo import fields, models


class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    td_completion_act_check = fields.Boolean(
        string='Checking the completion act',
        default=False
    )
