from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    td_untaxed_price_unit = fields.Float(
        string="Untaxed Price Unit",
        compute='_compute_td_untaxed_price_unit',
        store=True
    )

    @api.depends('price_unit', 'tax_id')
    def _compute_td_untaxed_price_unit(self):
        for line in self:
            taxes = line.tax_id.compute_all(line.price_unit, quantity=1.0, product=line.product_id, partner=line.order_id.partner_id)
            line.td_untaxed_price_unit = taxes['total_excluded']
