from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id', 'currency_id')
    def _compute_amount(self):
        AccountTax = self.env["account.tax"]
        for line in self:
            if line.display_type:
                line.price_subtotal = 0.0
                line.price_tax = 0.0
                line.price_total = 0.0
                continue

            base_line = line._prepare_base_line_for_taxes_computation()
            AccountTax._add_tax_details_in_base_line(base_line, line.company_id)

            td = base_line.get("tax_details") or {}
            subtotal = td.get("raw_total_excluded_currency")
            total = td.get("raw_total_included_currency")

            if subtotal is None:
                subtotal = td.get("total_excluded_currency", 0.0)
            if total is None:
                total = td.get("total_included_currency", subtotal)

            line.price_subtotal = subtotal
            line.price_total = total
            line.price_tax = total - subtotal
