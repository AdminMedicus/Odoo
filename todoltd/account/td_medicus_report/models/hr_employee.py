from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    td_partner_short_name = fields.Char(
        string='Short Name'
    )

    td_driver_license_number = fields.Char(
        string='Driver License Number',
        related='work_contact_id.td_driver_license_number',
        readonly=False,
    )
