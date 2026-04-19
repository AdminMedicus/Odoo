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

    @api.depends('partner_id')
    def _compute_partner_id_td(self):
        for rec in self:
            if rec.partner_id:
                rec.td_parent_partner_id = rec.partner_id.id

    def button_validate(self):
        # Block delivery validation until user clicked "Ready to be completed" on the SO.
        # This block must apply to outgoing only (delivery to customer).
        for picking in self:
            if (
                picking.picking_type_code == 'outgoing'
                and picking.sale_id
                and not picking.sale_id.stock_status_assigned
            ):
                raise UserError(_(
                    'Спочатку натисніть "Ready to be completed" ("Готовий до комплектації") у Sales Order. '
                    'Після цього можна підтвердити доставку.'
                ))

        res = super().button_validate()

        # Propagate sub_client to chained pickings (keep old behavior)
        picking_ids = self.move_ids.move_dest_ids.picking_id
        for picking in picking_ids:
            picking.sub_client_id = self.sub_client_id.id

        # Disable the stock status button:
        # - ship_only (1-step): after outgoing validate
        # - pick_ship (2-step): after internal validate (old behavior)
        # - pick_pack_ship (3-step): after ALL internal pickings are done (new nuance)
        if self.sale_id:
            steps = getattr(self.sale_id.warehouse_id, "delivery_steps", False)

            if steps == 'ship_only':
                if self.picking_type_code == 'outgoing':
                    self.sale_id.stock_button_active = False

            elif steps == 'pick_ship':
                if self.picking_type_code == 'internal':
                    self.sale_id.stock_button_active = False

            elif steps == 'pick_pack_ship':
                if self.picking_type_code == 'internal':
                    internal_left = self.sale_id.picking_ids.filtered(
                        lambda p: p.picking_type_code == 'internal' and p.state not in ('done', 'cancel')
                    )
                    if not internal_left:
                        self.sale_id.stock_button_active = False

            else:
                # Fallback: keep your previous logic
                has_internal = bool(self.sale_id.picking_ids.filtered(lambda p: p.picking_type_code == 'internal'))
                if self.picking_type_code == 'internal' or (self.picking_type_code == 'outgoing' and not has_internal):
                    self.sale_id.stock_button_active = False

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
