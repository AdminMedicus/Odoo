from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _td_has_tax_included_override(self):
        self.ensure_one()
        return any(tax.price_include_override == "tax_included" for tax in self.tax_id)

    @api.depends("product_uom_qty", "discount", "price_unit", "tax_id", "currency_id")
    def _compute_amount(self):
        AccountTax = self.env["account.tax"]

        for line in self:
            if line.display_type:
                line.price_subtotal = 0.0
                line.price_tax = 0.0
                line.price_total = 0.0
                continue

            if not line._td_has_tax_included_override():
                price_unit_disc = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
                taxes_res = line.tax_id.compute_all(
                    price_unit_disc,
                    currency=line.currency_id,
                    quantity=line.product_uom_qty,
                    product=line.product_id,
                    partner=line.order_id.partner_shipping_id,
                )
                line.price_subtotal = taxes_res["total_excluded"]
                line.price_total = taxes_res["total_included"]
                line.price_tax = line.price_total - line.price_subtotal
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

    @api.depends("price_unit", "discount", "tax_id")
    def _compute_td_untaxed_price_unit(self):
        for line in self:
            price_unit_disc = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)

            if not line.tax_id:
                line.td_untaxed_price_unit = price_unit_disc
                continue

            if not line._td_has_tax_included_override():
                line.td_untaxed_price_unit = price_unit_disc
                continue

            included_taxes = line.tax_id.filtered(
                lambda tax: tax.price_include_override == "tax_included" and tax.amount_type == "percent"
            )

            if not included_taxes:
                line.td_untaxed_price_unit = price_unit_disc
                continue

            rate = sum(included_taxes.mapped("amount")) / 100.0
            if not rate:
                line.td_untaxed_price_unit = price_unit_disc
                continue

            currency = line.currency_id or line.order_id.currency_id or line.company_id.currency_id
            line.td_untaxed_price_unit = currency.round(price_unit_disc / (1.0 + rate))

    def _prepare_invoice_line(self, **optional_values):
        """
        Fix for td_medicus_1c_integration:
        that module always replaces invoice line price_unit with price_subtotal / qty.
        This is wrong for tax-included prices because subtotal is untaxed,
        so invoice gets 1682.24 instead of original 1800.00.

        Rules:
        - tax_included -> keep original price_unit from super()
        - tax_excluded/default -> keep their "exact subtotal per unit" logic
        """
        self.ensure_one()
        res = super()._prepare_invoice_line(**optional_values)

        quantity = optional_values.get("quantity", self.product_uom_qty) or self.product_uom_qty or 0.0
        if not quantity:
            return res

        if self._td_has_tax_included_override():
            # Do NOT overwrite price_unit for tax-included scenario.
            # It must stay gross/original (e.g. 1800.00)
            return res

        if self.price_subtotal:
            res["price_unit"] = self.price_subtotal / quantity

        return res
