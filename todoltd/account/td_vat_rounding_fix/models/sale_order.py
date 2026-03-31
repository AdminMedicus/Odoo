from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends(
        "order_line.price_subtotal",
        "order_line.price_tax",
        "order_line.price_total",
        "currency_id",
        "company_id",
        "payment_term_id",
    )
    def _compute_amounts(self):
        AccountTax = self.env["account.tax"]

        for order in self:
            order_lines = order.order_line.filtered(
                lambda line: not line.display_type and not line.is_downpayment
            )
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()

            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)

            tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                company=order.company_id,
                currency=order.currency_id or order.company_id.currency_id,
            )

            order.amount_untaxed = tax_totals["base_amount_currency"]
            order.amount_tax = tax_totals["tax_amount_currency"]
            order.amount_total = tax_totals["total_amount_currency"]

    @api.depends_context("lang")
    @api.depends(
        "amount_total",
        "amount_untaxed",
        "amount_tax",
        "order_line.price_subtotal",
        "order_line.price_tax",
        "order_line.price_total",
        "currency_id",
        "company_id",
    )
    def _compute_tax_totals(self):
        AccountTax = self.env["account.tax"]

        for order in self:
            order_lines = order.order_line.filtered(
                lambda line: not line.display_type and not line.is_downpayment
            )
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()

            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)

            order.tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                company=order.company_id,
                currency=order.currency_id or order.company_id.currency_id,
            )