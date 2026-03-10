from odoo import api, models


class TdTaxInvoiceLine(models.Model):
    _inherit = "td.tax.invoice.line"

    @api.depends("product_id", "lot_ids", "vat_id", "quantity", "invoice_line_id", "td_sale_order_line_id")
    def _compute_product_id(self):
        for line in self:
            product = line.product_id
            if not product:
                line.price_with_out_vat = 0.0
                line.sum_price_with_out_vat = 0.0
                line.vat_price = 0.0
                line.sum_vat_price = 0.0
                line.sum_price_with_vat = 0.0
                line.uktzed_code_id = False
                continue

            line.name = product.description

            currency = (
                line.invoice_currency_id
                or line.sale_order_currency_id
                or line.env.company.currency_id
            )
            qty = line.quantity or line.invoice_quantity or line.sale_order_quantity or 0.0
            tax_rate = (line.vat_id.amount or 0.0) / 100.0

            invoice_line = line.invoice_line_id
            sale_line = line.td_sale_order_line_id

            if line.vat_type == "tax_included":
                source_subtotal = 0.0
                source_total = 0.0

                if invoice_line:
                    source_subtotal = invoice_line.price_subtotal or 0.0
                    source_total = invoice_line.price_total or 0.0
                    source_qty = invoice_line.quantity or 0.0
                elif sale_line:
                    source_subtotal = sale_line.price_subtotal or 0.0
                    source_total = sale_line.price_total or 0.0
                    source_qty = sale_line.product_uom_qty or 0.0
                else:
                    source_qty = 0.0

                # Если количество совпадает с источником — берем уже готовые totals из source line
                if invoice_line and qty == source_qty:
                    line.sum_price_with_out_vat = currency.round(source_subtotal)
                    line.sum_price_with_vat = currency.round(source_total)
                    line.sum_vat_price = currency.round(
                        line.sum_price_with_vat - line.sum_price_with_out_vat
                    )
                elif sale_line and qty == source_qty:
                    line.sum_price_with_out_vat = currency.round(source_subtotal)
                    line.sum_price_with_vat = currency.round(source_total)
                    line.sum_vat_price = currency.round(
                        line.sum_price_with_vat - line.sum_price_with_out_vat
                    )
                else:
                    gross_unit = 0.0
                    if invoice_line:
                        gross_unit = invoice_line.price_unit or 0.0
                    elif sale_line:
                        gross_unit = sale_line.price_unit or 0.0

                    gross_total = currency.round(gross_unit * qty)
                    untaxed_total = (
                        currency.round(gross_total / (1.0 + tax_rate))
                        if tax_rate else gross_total
                    )
                    vat_total = currency.round(gross_total - untaxed_total)

                    line.sum_price_with_out_vat = untaxed_total
                    line.sum_vat_price = vat_total
                    line.sum_price_with_vat = currency.round(
                        line.sum_price_with_out_vat + line.sum_vat_price
                    )

                if qty:
                    line.price_with_out_vat = currency.round(line.sum_price_with_out_vat / qty)
                    line.vat_price = currency.round(line.sum_vat_price / qty)
                else:
                    line.price_with_out_vat = 0.0
                    line.vat_price = 0.0

            else:
                unit_untaxed = 0.0

                if invoice_line:
                    unit_untaxed = invoice_line.td_untaxed_price_unit or invoice_line.price_unit or 0.0
                elif sale_line:
                    unit_untaxed = sale_line.td_untaxed_price_unit or sale_line.price_unit or 0.0
                else:
                    unit_untaxed = line.price_with_out_vat or 0.0

                line.price_with_out_vat = currency.round(unit_untaxed)
                line.sum_price_with_out_vat = currency.round(unit_untaxed * qty)
                line.sum_vat_price = currency.round(line.sum_price_with_out_vat * tax_rate)
                line.sum_price_with_vat = currency.round(
                    line.sum_price_with_out_vat + line.sum_vat_price
                )

                if qty:
                    line.vat_price = currency.round(line.sum_vat_price / qty)
                else:
                    line.vat_price = 0.0

            if line.lot_ids:
                line.uktzed_code_id = line.lot_ids[0].td_uktzed_code_id.id or False
            elif product.td_uktzed_code_id:
                line.uktzed_code_id = product.td_uktzed_code_id.id
            else:
                line.uktzed_code_id = False
