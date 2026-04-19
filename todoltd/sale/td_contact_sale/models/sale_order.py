from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


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
    # stock_status_assigned = fields.Boolean(default=False)
    stock_button_active = fields.Boolean(default=True)

    @api.onchange('partner_id')
    def _onchange_domain_for_sub_client_id(self):
        for res in self:
            if res.partner_id:
                res.allowed_sub_client_ids = (
                    res.partner_id.sub_client_rel_ids.sub_client_id.ids
                    or False
                )
                typical = res.partner_id.sub_client_rel_ids.filtered(
                    lambda rec: rec.is_typical
                )
                if typical:
                    res.sub_client_id = typical.sub_client_id.id
                else:
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
            elif res.sub_client_id:
                res.partner_shipping_id = res.sub_client_id.id
                res.allowed_partner_shipping_id = [res.sub_client_id.id]
            else:
                res.partner_shipping_id = res.partner_id.id

    def action_confirm(self):
        action = super().action_confirm()

        for order in self:
            order.stock_button_active = True

            for picking in order.picking_ids:
                picking.sub_client_id = order.sub_client_id.id
                picking.partner_id = order.partner_shipping_id.id
                picking.td_parent_partner_id = order.partner_id.id

        return action

    def action_confirm_stock_status(self):
        """
        Unlock delivery validation after user clicked
        "Ready to be completed" on the Sales Order.
        """
        for order in self:
            order.stock_button_active = False

    def action_rejected_stock_status(self):
        """
        Lock delivery validation again after user clicked
        "Not ready to be completed" on the Sales Order.
        """
        for order in self:
            order.stock_button_active = True
