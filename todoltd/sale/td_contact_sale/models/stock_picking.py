from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sub_client_id = fields.Many2one(
        comodel_name='res.partner',
    )

    td_parent_partner_id = fields.Many2one(
        comodel_name='res.partner',
        compute='_compute_partner_id_td',
        store=True
    )

    allowed_sub_client_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='stock_picking_allowed_sub_client_rel',
        column1='stock_picking_id',
        column2='allowed_sub_client_id',
    )
    td_stock_ready_for_completion = fields.Boolean(
        string="Ready to be completed",
        compute="_compute_td_stock_ready_for_completion",
        store=True,
    )

    td_stock_ready_status = fields.Selection(
        selection=[
            ("ready", "Ready"),
            ("not_ready", "Not Ready"),
        ],
        string="Completion Status",
        compute="_compute_td_stock_ready_status",
        store=True,
    )

    @api.depends(
        "picking_type_code",
        "sale_id",
        "sale_id.stock_button_active",
    )
    def _compute_td_stock_ready_for_completion(self):
        for picking in self:
            if picking.picking_type_code == "outgoing" and picking.sale_id:
                picking.td_stock_ready_for_completion = not picking.sale_id.stock_button_active
            else:
                picking.td_stock_ready_for_completion = False

    @api.depends(
        "picking_type_code",
        "sale_id",
        "sale_id.stock_button_active",
    )
    def _compute_td_stock_ready_status(self):
        for picking in self:
            if picking.picking_type_code == "outgoing" and picking.sale_id:
                if picking.sale_id.stock_button_active:
                    picking.td_stock_ready_status = "not_ready"
                else:
                    picking.td_stock_ready_status = "ready"
            else:
                picking.td_stock_ready_status = False

    @api.depends('partner_id')
    def _compute_partner_id_td(self):
        for rec in self:
            if rec.partner_id:
                rec.td_parent_partner_id = rec.partner_id.id

    def button_validate(self):
        """
        Block delivery validation until user clicked "Ready to be completed" on the SO.
        This block must apply to outgoing only (delivery to customer).
        """
        for picking in self:
            if not picking.user_id:
                picking.user_id = self.env.user.id
            if (
                picking.picking_type_code == 'outgoing'
                and picking.sale_id
                and picking.sale_id.stock_button_active
            ):
                raise UserError(_(
                    "You must click 'Ready to be completed' on the Sales Order before validating the delivery."
                ))

        res = super().button_validate()

        # Propagate sub_client to chained pickings (keep old behavior)
        picking_ids = self.move_ids.move_dest_ids.picking_id
        for picking in picking_ids:
            picking.sub_client_id = self.sub_client_id.id

        return res

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
