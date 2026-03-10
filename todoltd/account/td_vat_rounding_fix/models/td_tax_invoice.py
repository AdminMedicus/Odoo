from odoo import api, models


class TdTaxInvoice(models.Model):
    _inherit = "td.tax.invoice"

    def _td_get_currency(self):
        self.ensure_one()

        currency = False

        if "invoice_id" in self._fields and self.invoice_id and self.invoice_id.currency_id:
            currency = self.invoice_id.currency_id
        elif "sale_order_id" in self._fields and self.sale_order_id and self.sale_order_id.currency_id:
            currency = self.sale_order_id.currency_id
        elif "currency_id" in self._fields and self.currency_id:
            currency = self.currency_id

        return currency or self.env.company.currency_id

    @api.depends(
        "td_invoice_line_ids.sum_price_with_out_vat",
        "td_invoice_line_ids.sum_vat_price",
        "td_invoice_line_ids.sum_price_with_vat",
    )
    def _compute_total_price(self):
        for inv in self:
            currency = inv._td_get_currency()

            inv.price_with_out_tax = currency.round(
                sum(inv.td_invoice_line_ids.mapped("sum_price_with_out_vat"))
            )
            inv.price_vat = currency.round(
                sum(inv.td_invoice_line_ids.mapped("sum_vat_price"))
            )
            inv.price_total = currency.round(
                sum(inv.td_invoice_line_ids.mapped("sum_price_with_vat"))
            )

    @api.onchange("tax_guide_id")
    def _onchange_tax_guide_id(self):
        for inv in self:
            inv.td_invoice_line_ids._compute_product_id()
            inv._compute_total_price()