from collections import defaultdict
import logging
from odoo import models, fields, api, Command


_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale Order',
        # related='sale_line_id.order_id',
        compute='_compute_sale_order_id',
        store=True
    )
    td_price_unit = fields.Float(
        compute='_compute_td_price_unit',
        store=True,
        readonly=False
    )
    td_price_subtotal = fields.Float(
        compute='_compute_td_price_unit',
        store=True
    )
    td_lot_ids = fields.Many2many(
        comodel_name='stock.lot'
    )
    td_uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed',
        compute='_compute_product_id_and_lot_ids',
        readonly=False
    )
    td_quantity = fields.Float()
    td_picking_type_id = fields.Many2one(
        comodel_name='stock.picking.type',
        related='picking_id.picking_type_id'
    )
    td_picking_code = fields.Selection(
        [
            ('incoming', 'Incoming'),
            ('outgoing', 'Outcoming'),
            ('internal', 'Internal')
        ],
        compute='_compute_td_picking_code'
    )
    td_untaxed_price_unit = fields.Float(
        string="Untaxed Price Unit",
        compute='_compute_td_price_unit',
        store=True
    )

    @api.depends('purchase_line_id','sale_line_id', 'product_id', 'quantity')
    def _compute_td_price_unit(self):
        for line in self:
            if line.bom_line_id:
                line.td_price_unit = line.bom_line_id.price_unit
                line.td_untaxed_price_unit = line.bom_line_id.td_untaxed_price_unit
            elif line.sale_line_id:
                line.td_price_unit = line.sale_line_id.price_unit
                line.td_untaxed_price_unit = line.sale_line_id.td_untaxed_price_unit
            elif line.purchase_line_id:
                line.td_price_unit = line.purchase_line_id.price_unit
                line.td_untaxed_price_unit = line.purchase_line_id.td_untaxed_price_unit
            else:
                line.td_price_unit = line.td_price_unit
                line.td_untaxed_price_unit = line.td_untaxed_price_unit

            line.td_price_subtotal = line.td_untaxed_price_unit * line.quantity

    @api.depends('td_picking_type_id')
    @api.onchange('td_picking_type_id')
    def _compute_td_picking_code(self):
        for line in self:
            if line.td_picking_type_id and line.td_picking_type_id.code:
                try:
                    line.td_picking_code = line.td_picking_type_id.code
                except Exception as e:
                    line.td_picking_code = 'internal'
                    _logger.info(e)
            else:
                line.td_picking_code = 'internal'

    @api.depends('sale_line_id')
    def _compute_sale_order_id(self):
        for rec in self:
            if rec.sale_line_id:
                rec.sale_order_id = rec.sale_line_id.order_id.id

    @api.depends(
        'td_lot_ids', 'move_line_ids.lot_id', 'move_line_ids.quantity'
    )
    def _compute_lot_ids(self):
        for move in self:
            if move.td_lot_ids:
                move.lot_ids = move.td_lot_ids
            else:
                domain = [
                    ('move_id', '=', move.id),
                    ('lot_id', '!=', False),
                    ('quantity', '!=', 0.0)
                ]
                lots = self.env['stock.move.line'].search(domain).mapped(
                    'lot_id'
                )
                move.lot_ids = lots

    def _set_lot_ids(self):
        for move in self:
            if move.picking_id and move.picking_id.picking_type_code == 'incoming':
                # Incoming receipts must not auto-fill lot_name.
                # The user enters lot_name manually and validation creates/uses that lot.
                continue

            lots_to_process = move.td_lot_ids if move.td_lot_ids else move.lot_ids
            move_lines_commands = []

            mls = move.move_line_ids
            mls_with_lots = mls.filtered(lambda ml: ml.lot_id)
            mls_without_lots = (mls - mls_with_lots)

            existing_lot_ids = mls.mapped('lot_id')

            for lot in lots_to_process:
                if lot not in existing_lot_ids:
                    qty_per_lot = 1.0 if move.product_id.tracking == 'serial' else move.td_quantity

                    qty_to_assign = qty_per_lot if move.product_id.tracking == 'serial' else move.td_quantity

                    if mls_without_lots:
                        move_line = mls_without_lots[0]
                        move_lines_commands.append(
                            Command.update(move_line.id, {
                                'lot_name': lot.name,
                                'lot_id': lot.id,
                                'product_uom_id': move.product_id.uom_id.id,
                                'quantity': qty_to_assign,
                            }))
                        mls_without_lots = mls_without_lots[1:]
                    else:
                        reserved_quants = self.env['stock.quant']._get_reserve_quantity(
                            move.product_id, move.location_id, qty_to_assign, lot_id=lot
                        )
                        if reserved_quants:
                            move_line_vals = move._prepare_move_line_vals(
                                quantity=qty_to_assign,
                                reserved_quant=reserved_quants[0][0]
                            )
                        else:
                            move_line_vals = move._prepare_move_line_vals(quantity=qty_to_assign)
                            move_line_vals['lot_id'] = lot.id
                            move_line_vals['lot_name'] = lot.name

                        move_line_vals['product_uom_id'] = move.product_id.uom_id.id
                        move_lines_commands.append((0, 0, move_line_vals))
                else:
                    move_line = mls.filtered(lambda line: line.lot_id.id == lot.id)
                    qty_per_lot = 1.0 if move.product_id.tracking == 'serial' else move.td_quantity
                    move_line.quantity = qty_per_lot

            if move_lines_commands:
                move.write({'move_line_ids': move_lines_commands})

    @api.depends('move_line_ids.quantity', 'move_line_ids.product_uom_id')
    def _compute_quantity(self):
        """ This field represents the sum of the move lines `quantity`. It allows the user to know
        if there is still work to do.

        We take care of rounding this value at the general decimal precision and not the rounding
        of the move's UOM to make sure this value is really close to the real sum, because this
        field will be used in `_action_done` in order to know if the move will need a backorder or
        an extra move.
        """
        if not any(self._ids):
            # onchange
            for move in self:
                if move.td_quantity:
                    move.quantity = move.td_quantity
                    continue
                move.quantity = move._quantity_sml()
        else:
            # compute
            move_lines_ids = set()
            for move in self:
                if move.td_quantity:
                    move.quantity = move.td_quantity
                    continue
                move_lines_ids |= set(move.move_line_ids.ids)

            data = self.env['stock.move.line']._read_group(
                [('id', 'in', list(move_lines_ids))],
                ['move_id', 'product_uom_id'], ['quantity:sum']
            )
            sum_qty = defaultdict(float)
            for move, product_uom, qty_sum in data:
                uom = move.product_uom
                sum_qty[move.id] += product_uom._compute_quantity(qty_sum, uom, round=False)

            for move in self:
                move.quantity = sum_qty[move.id]

    @api.onchange('td_uktzed_code_id')
    def _onchange_td_uktzed_code_id(self):
        for line in self:
            if line.lot_ids:
                for lot in line.lot_ids:
                    lot.browse(lot._origin.id).td_uktzed_code_id = line.td_uktzed_code_id.id

    @api.onchange('lot_ids', 'product_id')
    def _compute_product_id_and_lot_ids(self):
        for line in self:
            product = line.product_id
            if line.lot_ids:
                line.td_uktzed_code_id = (
                    line.lot_ids[0].td_uktzed_code_id.id or False
                )
            if not line.td_uktzed_code_id:
                if product.td_uktzed_code_id:
                    line.td_uktzed_code_id = product.td_uktzed_code_id.id
                else:
                    line.td_uktzed_code_id = False
