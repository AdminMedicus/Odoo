from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

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
