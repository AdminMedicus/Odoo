from odoo import models, fields, api


class TdStockMove(models.TransientModel):
    _name = "td.agreement.stock.move"
    _description = "ToDo Wizard Stock Move"

    is_selected = fields.Boolean()

    move_id = fields.Many2one(
        comodel_name='stock.move',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
    )
    lot_ids = fields.Many2many(
        comodel_name='stock.lot'
    )
    sale_line_id = fields.Many2one(
        comodel_name='sale.order.line'
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
    )
    quantity = fields.Float()
    product_uom = fields.Many2one(
        comodel_name='uom.uom',
    )
    stock_picking_id = fields.Many2one(
        comodel_name='stock.picking',
    )
    origin_stock_picking_id = fields.Many2one(
        comodel_name='stock.picking',
    )
    price_unit = fields.Float()
    price_subtotal = fields.Float(
        compute='_compute_quantity',
    )

    def action_process_selected(self):
        records = self.env['stock.move'].sudo().create([
            {
                'picking_id': rec.origin_stock_picking_id.id,
                'product_id': rec.product_id.id,
                'quantity': rec.quantity,
                'td_quantity': rec.quantity,
                'td_lot_ids': [(6, 0, rec.lot_ids.ids)],
                'sale_line_id': rec.sale_line_id.id,
                'sale_order_id': rec.sale_order_id.id,
                'product_uom': rec.product_uom.id,
                'name': rec.product_id.name,
                'td_price_unit': rec.price_unit,
                'td_price_subtotal': rec.price_subtotal,
            } for rec in self
        ])
        for record in records:
            record.write({
                'lot_ids': [(6, 0, record.td_lot_ids.ids)],
                'quantity': record.td_quantity,
            })
        self.origin_stock_picking_id.action_confirm()

    @api.onchange('quantity')
    def _compute_quantity(self):
        for rec in self:
            rec.price_subtotal = rec.price_unit * rec.quantity
