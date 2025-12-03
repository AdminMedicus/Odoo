from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = "res.partner"

    region_id = fields.Many2one(
        comodel_name='td.res.country.region'
    )
    full_partner_name = fields.Char()
    td_short_name = fields.Char(
        string='Short Name',
    )
    sub_client_rel_ids = fields.One2many(
        comodel_name='td.res.partner.sub.client.rel',
        inverse_name='partner_id',
    )

    @api.onchange('sub_client_rel_ids')
    def _onchange_sub_client_rel_ids(self):
        for partner in self:
            typical_len = len(
                partner.sub_client_rel_ids.filtered(
                    lambda res: res.is_typical
                )
            )
            if typical_len > 1:
                raise ValidationError(_(
                    "This client can have only 1 typical subclient"
                ))
