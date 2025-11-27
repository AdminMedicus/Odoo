from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    td_license_number = fields.Char(
        string='License Number'
    )
    td_license_date = fields.Date(
        string='License Date'
    )
    td_license_issued_by = fields.Char(
        string='License Issued By'
    )
    