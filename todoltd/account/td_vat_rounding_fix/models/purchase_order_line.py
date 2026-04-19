from odoo import api, models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _td_has_tax_included_override(self):
        self.ensure_one()
        return any(tax.price_include_override == "tax_included" for tax in self.taxes_id)

    @api.depends("price_unit", "taxes_id")
    def _compute_td_untaxed_price_unit(self):
        for line in self:
            if not line.taxes_id:
                line.td_untaxed_price_unit = line.price_unit
                continue

            if not line._td_has_tax_included_override():
                line.td_untaxed_price_unit = line.price_unit
                continue

            included_taxes = line.taxes_id.filtered(
                lambda tax: tax.price_include_override == "tax_included" and tax.amount_type == "percent"
            )

            if not included_taxes:
                line.td_untaxed_price_unit = line.price_unit
                continue

            rate = sum(included_taxes.mapped("amount")) / 100.0
            if not rate:
                line.td_untaxed_price_unit = line.price_unit
                continue

            currency = line.currency_id or line.order_id.currency_id or line.company_id.currency_id
            line.td_untaxed_price_unit = currency.round(line.price_unit / (1.0 + rate))
            