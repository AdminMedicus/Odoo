from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _td_has_tax_included_override(self):
        self.ensure_one()
        return any(
            tax.price_include_override == "tax_included"
            for tax in self.tax_ids
        )

    @api.depends("quantity", "discount", "price_unit", "tax_ids", "currency_id")
    def _compute_totals(self):
        for line in self:
            if line.display_type not in ("product", "rounding"):
                line.price_subtotal = 0.0
                line.price_total = 0.0
                continue

            currency = line.currency_id or line.move_id.currency_id or line.company_id.currency_id
            quantity = line.quantity or 0.0
            discount = line.discount or 0.0
            price_unit_disc = line.price_unit * (1.0 - (discount / 100.0))

            # Обычная логика для tax excluded / default
            if not line._td_has_tax_included_override():
                taxes_res = line.tax_ids.compute_all(
                    price_unit_disc,
                    currency=currency,
                    quantity=quantity,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.move_id.move_type in ("out_refund", "in_refund"),
                )
                line.price_subtotal = taxes_res["total_excluded"]
                line.price_total = taxes_res["total_included"]
                continue

            # Кастомная логика для tax included
            included_taxes = line.tax_ids.filtered(
                lambda tax: tax.price_include_override == "tax_included" and tax.amount_type == "percent"
            )

            if not included_taxes:
                taxes_res = line.tax_ids.compute_all(
                    price_unit_disc,
                    currency=currency,
                    quantity=quantity,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.move_id.move_type in ("out_refund", "in_refund"),
                )
                line.price_subtotal = taxes_res["total_excluded"]
                line.price_total = taxes_res["total_included"]
                continue

            rate = sum(included_taxes.mapped("amount")) / 100.0
            if not rate:
                taxes_res = line.tax_ids.compute_all(
                    price_unit_disc,
                    currency=currency,
                    quantity=quantity,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.move_id.move_type in ("out_refund", "in_refund"),
                )
                line.price_subtotal = taxes_res["total_excluded"]
                line.price_total = taxes_res["total_included"]
                continue

            untaxed_unit = currency.round(price_unit_disc / (1.0 + rate))
            subtotal = currency.round(untaxed_unit * quantity)
            total = currency.round(price_unit_disc * quantity)

            line.price_subtotal = subtotal
            line.price_total = total

    @api.depends("price_unit", "discount", "tax_ids")
    def _compute_td_untaxed_price_unit(self):
        for line in self:
            currency = line.currency_id or line.move_id.currency_id or line.company_id.currency_id
            discount = line.discount or 0.0
            price_unit_disc = line.price_unit * (1.0 - (discount / 100.0))

            if not line.tax_ids:
                line.td_untaxed_price_unit = price_unit_disc
                continue

            if not line._td_has_tax_included_override():
                line.td_untaxed_price_unit = price_unit_disc
                continue

            included_taxes = line.tax_ids.filtered(
                lambda tax: tax.price_include_override == "tax_included" and tax.amount_type == "percent"
            )

            if not included_taxes:
                line.td_untaxed_price_unit = price_unit_disc
                continue

            rate = sum(included_taxes.mapped("amount")) / 100.0
            if not rate:
                line.td_untaxed_price_unit = price_unit_disc
                continue

            line.td_untaxed_price_unit = currency.round(price_unit_disc / (1.0 + rate))
