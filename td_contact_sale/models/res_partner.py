from odoo import models, fields


class Partner(models.Model):
    _inherit = "res.partner"

    region_id = fields.Many2one(
        comodel_name='td.res.country.region'
    )
    full_partner_name = fields.Char()
    sub_client_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='res_partner_sub_client_rel',
        column1='partner_id',
        column2='sub_client_id',
    )
