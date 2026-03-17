from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _description = "Account Move"
    _inherit = "account.move.line"

    td_untaxed_price_unit = fields.Float(
        string="Untaxed Price Unit",
        compute='_compute_td_untaxed_price_unit',
        store=True
    )

    @api.depends('price_unit', 'tax_ids')
    def _compute_td_untaxed_price_unit(self):
        for line in self:
            taxes = line.tax_ids.compute_all(line.price_unit, quantity=1.0, product=line.product_id, partner=line.move_id.partner_id)
            line.td_untaxed_price_unit = taxes['total_excluded']
