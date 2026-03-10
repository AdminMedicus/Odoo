from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _td_has_tax_included_override(self):
        self.ensure_one()
        product_lines = self.invoice_line_ids.filtered(lambda l: l.display_type == "product")
        taxes = product_lines.mapped("tax_ids")
        return any(tax.price_include_override == "tax_included" for tax in taxes)

    @api.depends_context("lang")
    @api.depends(
        "amount_total",
        "currency_id",
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.price_subtotal",
        "invoice_line_ids.price_total",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_payment_term_id",
        "partner_id",
    )
    def _compute_tax_totals(self):
        for move in self:
            if move.is_invoice(include_receipts=True):
                base_lines, _tax_lines = move._get_rounded_base_and_tax_lines()
                summary = self.env["account.tax"]._get_tax_totals_summary(
                    base_lines=base_lines,
                    company=move.company_id,
                    currency=move.currency_id,
                    cash_rounding=move.invoice_cash_rounding_id,
                )

                summary["display_in_company_currency"] = (
                    move.company_id.display_invoice_tax_company_currency
                    and move.company_currency_id != move.currency_id
                    and summary["has_tax_groups"]
                    and move.is_sale_document(include_receipts=True)
                )

                if move._td_has_tax_included_override():
                    currency = move.currency_id or move.company_id.currency_id
                    expected_total = currency.round(move.amount_total)
                    current_total = currency.round(summary.get("total_amount_currency", 0.0))
                    delta = currency.round(expected_total - current_total)

                    if not currency.is_zero(delta):
                        summary["total_amount_currency"] = expected_total
                        summary["base_amount_currency"] = currency.round(
                            summary.get("base_amount_currency", 0.0) + delta
                        )

                        if "same_tax_base" in summary:
                            summary["same_tax_base"] = False

                        # optional nested subtotals correction for UI
                        subtotals = summary.get("subtotals") or []
                        if subtotals:
                            first_subtotal = subtotals[0]
                            if "taxable_amount_currency" in first_subtotal:
                                first_subtotal["taxable_amount_currency"] = currency.round(
                                    first_subtotal.get("taxable_amount_currency", 0.0) + delta
                                )
                            if "base_amount_currency" in first_subtotal:
                                first_subtotal["base_amount_currency"] = currency.round(
                                    first_subtotal.get("base_amount_currency", 0.0) + delta
                                )

                move.tax_totals = summary
                move.td_tax_totals = summary
            else:
                move.tax_totals = None
                move.td_tax_totals = None

    @api.depends_context("lang")
    @api.depends(
        "currency_id",
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.price_subtotal",
        "invoice_line_ids.price_total",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_payment_term_id",
        "partner_id",
    )
    def _compute_td_tax_totals(self):
        self._compute_tax_totals()