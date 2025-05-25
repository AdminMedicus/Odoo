from odoo import models, fields


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
