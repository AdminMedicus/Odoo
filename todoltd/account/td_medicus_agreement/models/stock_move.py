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

    @api.depends('sale_line_id')
    def _compute_sale_order_id(self):
        for rec in self:
            if rec.sale_line_id:
                rec.sale_order_id = rec.sale_line_id.order_id.id
