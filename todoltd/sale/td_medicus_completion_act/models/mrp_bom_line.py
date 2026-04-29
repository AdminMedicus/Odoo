from odoo import api, fields, models


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    price_unit = fields.Float(
        string='Price Unit'
    )
    td_untaxed_price_unit = fields.Float(
        string='Untaxed Price Unit'
    )
    td_taxes_total = fields.Float(
        compute='_compute_td_price_subtotal',
        store=True,
        string='Total Taxes',
    )
    td_price_subtotal = fields.Float(
        compute='_compute_td_price_subtotal',
        store=True,
        string='Total Price',
    )
    td_untaxed_total = fields.Float(
        compute='_compute_td_price_subtotal',
        readonly=False,
        store=True,
        string='Untaxed Total'
    )

    @api.depends('price_unit', 'td_untaxed_price_unit', 'product_qty')
    def _compute_td_price_subtotal(self):
        for line in self:
            line.td_price_subtotal = line.price_unit * line.product_qty
            line.td_untaxed_total = line.td_untaxed_price_unit * line.product_qty
            line.td_taxes_total = abs(line.price_unit - line.td_untaxed_price_unit) * line.product_qty
