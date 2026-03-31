from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _add_tax_details_in_base_line(self, base_line, company, **kwargs):
        super()._add_tax_details_in_base_line(base_line, company, **kwargs)

        if getattr(company, "tax_calculation_rounding_method", None) != "round_globally":
            return

        taxes = base_line.get("taxes") or base_line.get("tax_ids")
        if not taxes:
            return

        if not isinstance(taxes, models.BaseModel):
            taxes = self.env["account.tax"].browse([int(x) for x in taxes])

        included_percent_taxes = taxes.filtered(
            lambda tax: tax.price_include_override == "tax_included" and tax.amount_type == "percent"
        )
        if not included_percent_taxes:
            return

        currency = base_line.get("currency") or base_line.get("currency_id") or company.currency_id
        if isinstance(currency, int):
            currency = self.env["res.currency"].browse(currency)

        quantity = base_line.get("quantity") or 0.0
        if not quantity:
            return

        price_unit = base_line.get("price_unit") or 0.0
        discount = base_line.get("discount") or 0.0
        discounted_price_unit = price_unit * (1.0 - (discount / 100.0))

        rate = sum(included_percent_taxes.mapped("amount")) / 100.0
        if not rate:
            return

        unit_excluded = currency.round(discounted_price_unit / (1.0 + rate))
        total_excluded = currency.round(unit_excluded * quantity)

        tax_details = base_line.get("tax_details") or {}

        for key in (
            "raw_total_excluded_currency",
            "base_amount_currency",
            "total_excluded_currency",
        ):
            if key in tax_details:
                tax_details[key] = total_excluded

        if "raw_base_amount_currency" in tax_details:
            tax_details["raw_base_amount_currency"] = total_excluded
        if "base_amount" in tax_details:
            tax_details["base_amount"] = total_excluded
        if "raw_base_amount" in tax_details:
            tax_details["raw_base_amount"] = total_excluded

        base_line["tax_details"] = tax_details
