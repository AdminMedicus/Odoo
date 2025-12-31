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

        incl_percent = taxes.filtered(lambda t: t.price_include and t.amount_type == "percent")
        if not incl_percent:
            return

        currency = base_line.get("currency") or base_line.get("currency_id") or company.currency_id
        if isinstance(currency, int):
            currency = self.env["res.currency"].browse(currency)

        qty = base_line.get("quantity") or 0.0
        if not qty:
            return

        price_unit = base_line.get("price_unit") or 0.0
        discount = base_line.get("discount") or 0.0
        price_unit_disc = price_unit * (1.0 - (discount / 100.0))

        rate = sum(incl_percent.mapped("amount")) / 100.0
        if not rate:
            return

        unit_excl = currency.round(price_unit_disc / (1.0 + rate))
        total_excl = currency.round(unit_excl * qty)

        td = base_line.get("tax_details") or {}

        for k in ("raw_total_excluded_currency", "base_amount_currency", "total_excluded_currency"):
            if k in td:
                td[k] = total_excl

        base_line["tax_details"] = td
