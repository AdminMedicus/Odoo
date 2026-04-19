from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    td_untaxed_price_unit = fields.Float(
        string="Untaxed Price Unit",
        compute='_compute_td_untaxed_price_unit',
        store=True
    )

    @api.depends('price_unit', 'taxes_id')
    def _compute_td_untaxed_price_unit(self):
        for line in self:
            taxes = line.taxes_id.compute_all(line.price_unit, quantity=1.0, product=line.product_id, partner=line.order_id.partner_id)
            line.td_untaxed_price_unit = taxes['total_excluded']
