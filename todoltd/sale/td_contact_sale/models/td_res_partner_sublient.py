from odoo import models, fields


class PartnerSubClientRel(models.Model):
    _name = 'td.res.partner.sub.client.rel'
    _description = 'Subclients Relation'
    _rec_name = 'sub_client_id'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(
        related='sub_client_id.name',
    )
    city = fields.Char(
        related='sub_client_id.city',
    )
    phone = fields.Char(
        related='sub_client_id.phone',
    )
    mobile = fields.Char(
        related='sub_client_id.mobile',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        related='sub_client_id.user_id'
    )
    category_id = fields.Many2many(
        comodel_name='res.partner.category',
        related='sub_client_id.category_id'
    )
    sub_client_id = fields.Many2one(
        comodel_name='res.partner',
        required=True,
        ondelete='cascade'
    )
    is_typical = fields.Boolean(
        string='Typical Subclient'
    )
