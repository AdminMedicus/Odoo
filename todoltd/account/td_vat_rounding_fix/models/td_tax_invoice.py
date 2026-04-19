from odoo import api, models


class TdTaxInvoice(models.Model):
    _inherit = "td.tax.invoice"

    def _td_get_currency(self):
        self.ensure_one()

        line = self.td_invoice_line_ids[:1]
        if line:
            return (
                line.invoice_currency_id
                or line.sale_order_currency_id
                or self.env.company.currency_id
            )
        return self.env.company.currency_id

    def _td_get_source_total(self):
        self.ensure_one()

        invoice_lines = self.td_invoice_line_ids.mapped("invoice_line_id").filtered(lambda l: l.move_id)
        if invoice_lines:
            moves = invoice_lines.mapped("move_id")
            if len(moves) == 1:
                return moves.amount_total

        sale_lines = self.td_invoice_line_ids.mapped("td_sale_order_line_id").filtered(lambda l: l.order_id)
        if sale_lines:
            orders = sale_lines.mapped("order_id")
            if len(orders) == 1:
                return orders.amount_total

        return False

    @api.depends(
        "td_invoice_line_ids.sum_price_with_out_vat",
        "td_invoice_line_ids.sum_vat_price",
        "td_invoice_line_ids.sum_price_with_vat",
        "td_invoice_line_ids.invoice_line_id",
        "td_invoice_line_ids.td_sale_order_line_id",
    )
    def _compute_total_price(self):
        for inv in self:
            currency = inv._td_get_currency()

            untaxed = currency.round(sum(inv.td_invoice_line_ids.mapped("sum_price_with_out_vat")))
            total = currency.round(sum(inv.td_invoice_line_ids.mapped("sum_price_with_vat")))

            source_total = inv._td_get_source_total()
            if source_total is not False:
                total = currency.round(source_total)

            inv.price_with_out_tax = untaxed
            inv.price_total = total
            inv.price_vat = currency.round(inv.price_total - inv.price_with_out_tax)

    @api.onchange("tax_guide_id")
    def _onchange_tax_guide_id(self):
        for inv in self:
            inv.td_invoice_line_ids._compute_product_id()
            inv._compute_total_price()
