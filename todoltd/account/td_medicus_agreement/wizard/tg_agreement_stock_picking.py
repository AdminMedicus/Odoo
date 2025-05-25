from odoo import models, fields


class TdStockPicking(models.TransientModel):
    _name = "td.agreement.stock.picking"
    _description = "ToDo Wizard Stock Picking"

    record_ids = fields.Many2many(
        comodel_name='td.agreement.stock.move',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
    )
    stock_picking_id = fields.Many2one(
        comodel_name='stock.picking',
    )

    def action_process_selected(self):
        for record in self:
            stock_picking = record.stock_picking_id
            self.env['stock.move'].sudo().create([
                {
                    'picking_id': stock_picking.id,
                    'product_id': rec.product_id.id,
                    'quantity': rec.quantity,
                    'sale_order_id': rec.sale_order_id.id,
                    'product_uom': rec.product_uom.id,
                    'name': rec.product_id.name
                } for rec in record.record_ids.filtered(
                    lambda rec: rec.is_selected
                )
            ])
