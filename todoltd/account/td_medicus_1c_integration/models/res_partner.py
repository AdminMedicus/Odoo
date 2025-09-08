from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    td_manager_id = fields.Many2one(
        comodel_name='hr.employee'
    )
