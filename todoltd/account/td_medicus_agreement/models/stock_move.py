from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = "stock.move"

    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale Order',
        # related='sale_line_id.order_id',
        compute='_compute_sale_order_id',
        store=True
    )
    td_price_unit = fields.Float()
    td_price_subtotal = fields.Float()
    td_lot_ids = fields.Many2many(
        comodel_name='stock.lot'
    )
    td_uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed',
        compute='_compute_product_id_and_lot_ids'
    )

    @api.depends('sale_line_id')
    def _compute_sale_order_id(self):
        for rec in self:
            if rec.sale_line_id:
                rec.sale_order_id = rec.sale_line_id.order_id.id

    @api.depends('move_line_ids.lot_id', 'move_line_ids.quantity')
    def _compute_lot_ids(self):
        for line in self:
            super(StockMove, line)._compute_lot_ids()
            if line.td_lot_ids:
                line.lot_ids = [(6, 0, line.td_lot_ids.ids)]

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
