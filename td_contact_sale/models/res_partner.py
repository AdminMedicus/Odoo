from odoo import models, fields


class Partner(models.Model):
    _inherit = "res.partner"

    region_id = fields.Many2one(
        comodel_name='td.res.country.region'
    )
    full_partner_name = fields.Char()
