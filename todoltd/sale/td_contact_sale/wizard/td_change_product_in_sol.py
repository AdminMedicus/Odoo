from odoo import fields, models, api


class TdChangeProductInSOL(models.TransientModel):
    _name = 'td.change.product.in.sol'
    _description = 'TdChangeProductInSOL'

    td_sale_order_line = fields.Many2one(
        comodel_name='sale.order.line'
    )
    td_product_template_ids = fields.Many2many(
        comodel_name='product.template',
        compute='_compute_td_product_template_ids'
    )

    @api.depends('td_sale_order_line')
    def _compute_td_product_template_ids(self):
        for rec in self:
            rec.td_product_template_ids = rec.td_sale_order_line.product_template_id.td_product_template_ids.ids
