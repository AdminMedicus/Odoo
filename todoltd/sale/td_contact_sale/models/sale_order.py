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
    stock_status_assigned = fields.Boolean(default=False)
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

    # -------------------------------------------------------------------------
    # Helpers for 1/2/3-step delivery (ship_only / pick_ship / pick_pack_ship)
    # -------------------------------------------------------------------------
    def _td_get_delivery_steps(self):
        self.ensure_one()
        wh = self.warehouse_id
        return getattr(wh, "delivery_steps", False)

    def _td_get_pickings_to_control(self):
        """
        Which pickings are controlled by the button "Ready to be completed".

        Keep old logic:
        - pick_ship / pick_pack_ship -> control INTERNAL pickings
        Add new logic:
        - ship_only -> control OUTGOING pickings

        Fallback to existing pickings if expected type isn't found.
        """
        self.ensure_one()
        steps = self._td_get_delivery_steps()
        pickings = self.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])

        if steps == 'ship_only':
            controlled = pickings.filtered(lambda p: p.picking_type_code == 'outgoing')
            return controlled or pickings

        # pick_ship / pick_pack_ship (and unknown) -> old behavior: internal
        controlled = pickings.filtered(lambda p: p.picking_type_code == 'internal')
        return controlled or pickings

    def action_confirm(self):
        action = super().action_confirm()
        for res in self:
            if res.picking_ids:
                # keep original partner/sub-client propagation on ALL pickings
                for picking in res.picking_ids:
                    picking.sub_client_id = res.sub_client_id.id
                    picking.partner_id = res.partner_shipping_id.id
                    picking.td_parent_partner_id = res.partner_id.id

                # Preserve old behavior for pick_ship / pick_pack_ship (internal)
                # Add ship_only behavior (outgoing)
                pickings_to_control = res._td_get_pickings_to_control()

                for picking in pickings_to_control:
                    # Keep original behavior: force state to confirmed at SO confirmation.
                    # (This prevents proceeding until "Ready to be completed" is clicked.)
                    picking.state = 'confirmed'
        return action

    def action_confirm_stock_status(self):
        """
        Button: "Ready to be completed"
        - Old (pick_ship / pick_pack_ship): set internal to assigned (as your old logic)
        - New (ship_only): reserve outgoing via action_assign()
        """
        StockQuant = self.env['stock.quant']

        for order in self:
            if not order.stock_button_active:
                continue

            pickings_to_control = order._td_get_pickings_to_control()

            for picking in pickings_to_control.filtered(lambda p: p.state not in ("done", "cancel")):
                if picking.picking_type_code == "internal":
                    # Keep old behavior for internal pickings.
                    picking.state = "assigned"
                    continue

                # First, try standard Odoo reservation.
                picking.action_assign()
                picking.invalidate_recordset()

                for move in picking.move_ids.filtered(lambda m: m.state not in ("done", "cancel")):
                    move.invalidate_recordset()

                    # Do not override already reserved quantity.
                    if move.quantity:
                        continue

                    available_qty = StockQuant._get_available_quantity(
                        move.product_id,
                        move.location_id,
                        lot_id=False,
                        package_id=False,
                        owner_id=False,
                        strict=False,
                    )

                    if available_qty <= 0:
                        continue

                    qty_to_set = min(available_qty, move.product_uom_qty)

                    if qty_to_set <= 0:
                        continue

                    _logger.info(
                        "TD stock fallback reservation: order=%s picking=%s move=%s "
                        "available_qty=%s demand=%s qty_to_set=%s",
                        order.name,
                        picking.name,
                        move.id,
                        available_qty,
                        move.product_uom_qty,
                        qty_to_set,
                    )

                    move.quantity = qty_to_set
                    move.invalidate_recordset()

                    if not move.move_line_ids or not move.quantity:
                        _logger.warning(
                            "TD stock fallback reservation did not fully apply: "
                            "order=%s picking=%s move=%s state=%s quantity=%s move_lines=%s",
                            order.name,
                            picking.name,
                            move.id,
                            move.state,
                            move.quantity,
                            move.move_line_ids.ids,
                        )

                picking.invalidate_recordset()

            order.stock_status_assigned = True

    def action_rejected_stock_status(self):
        """
        Button: "Not ready to be completed"
        - Old (pick_ship / pick_pack_ship): set internal back to confirmed (as your old logic)
        - New (ship_only): unreserve outgoing and set to confirmed
        """
        for res in self:
            if res.stock_button_active:
                if res.picking_ids:
                    pickings_to_control = res._td_get_pickings_to_control()

                    for picking in pickings_to_control:
                        if picking.picking_type_code == 'internal':
                            # OLD LOGIC (2/3-step): keep as-is
                            picking.state = 'confirmed'
                        else:
                            # NEW LOGIC (1-step): unreserve and return to confirmed
                            try:
                                picking.do_unreserve()
                            except Exception:
                                pass
                            picking.state = 'confirmed'
                res.stock_status_assigned = False
