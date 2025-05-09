from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sub_client_id = fields.Many2one(
        comodel_name='res.partner',
    )
    allowed_sub_client_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='sale_order_allowed_sub_client_rel',
        column1='sale_order_id',
        column2='allowed_sub_client_id',
    )
    allowed_partner_shipping_id = fields.Many2many(
        comodel_name='res.partner',
        relation='sale_order_allowed_partner_shipping_rel'
    )

    @api.onchange('partner_id')
    def _onchange_domain_for_sub_client_id(self):
        for res in self:
            if res.partner_id:
                res.allowed_sub_client_ids = res.partner_id.sub_client_ids.ids or False
                res.sub_client_id = False
            else:
                res.allowed_sub_client_ids = False
                res.sub_client_id = False

    @api.onchange('sub_client_id')
    def _onchange_sub_client_id(self):
        for res in self:
            if res.sub_client_id and res.sub_client_id.child_ids:
                res.partner_shipping_id = res.sub_client_id.child_ids[0].id
                res.allowed_partner_shipping_id = (
                    res.sub_client_id.child_ids.ids
                )
            else:
                res.partner_shipping_id = False

    def action_confirm(self):
        action = super().action_confirm()
        for res in self:
            if res.picking_ids:
                for picking in res.picking_ids:
                    picking.sub_client_id = res.sub_client_id.id
                    picking.partner_id = res.partner_shipping_id.id
        return action
