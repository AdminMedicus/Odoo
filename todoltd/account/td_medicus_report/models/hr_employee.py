from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    td_partner_short_name = fields.Char(
        string='Short Name'
    )
