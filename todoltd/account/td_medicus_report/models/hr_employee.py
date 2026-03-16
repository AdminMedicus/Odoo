from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    td_partner_short_name = fields.Char(
        string='Short Name'
    )

    td_driver_license_number = fields.Char(
        string='Driver License Number',
        compute='_compute_td_driver_license_number',
        inverse='_inverse_td_driver_license_number',
        store=False,
    )

    def _compute_td_driver_license_number(self):
        for rec in self:
            partner = rec.user_id.partner_id if rec.user_id and rec.user_id.partner_id else False
            rec.td_driver_license_number = partner.td_driver_license_number if partner else False

    def _inverse_td_driver_license_number(self):
        for rec in self:
            partner = rec.user_id.partner_id if rec.user_id and rec.user_id.partner_id else False
            if partner:
                partner.td_driver_license_number = rec.td_driver_license_number
