from odoo import api, models


class TdTaxInvoiceLine(models.Model):
    _inherit = "td.tax.invoice.line"

    def _td_get_parent_invoice_field_name(self):
        for field_name, field in self._fields.items():
            if getattr(field, "type", None) == "many2one" and getattr(field, "comodel_name", None) == "td.tax.invoice":
                return field_name
        return False

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
                gross_unit = 0.0
                source_total = 0.0
                source_qty = 0.0

                if invoice_line:
                    gross_unit = invoice_line.price_unit or 0.0
                    source_total = invoice_line.price_total or 0.0
                    source_qty = invoice_line.quantity or 0.0
                elif sale_line:
                    gross_unit = sale_line.price_unit or 0.0
                    source_total = sale_line.price_total or 0.0
                    source_qty = sale_line.product_uom_qty or 0.0

                gross_total = currency.round(gross_unit * qty)

                if tax_rate:
                    untaxed_unit = currency.round(gross_unit / (1.0 + tax_rate))
                    untaxed_total = currency.round(untaxed_unit * qty)
                else:
                    untaxed_unit = gross_unit
                    untaxed_total = gross_total

                vat_total = currency.round(gross_total - untaxed_total)

                line.price_with_out_vat = untaxed_unit if qty else 0.0
                line.sum_price_with_out_vat = untaxed_total
                line.sum_vat_price = vat_total
                line.sum_price_with_vat = gross_total

                if qty:
                    line.vat_price = currency.round(line.sum_vat_price / qty)
                else:
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

        parent_field_name = self._td_get_parent_invoice_field_name()
        if not parent_field_name:
            return

        invoices = self.mapped(parent_field_name)
        for inv in invoices:
            currency = (
                inv.td_invoice_line_ids[:1].invoice_currency_id
                or inv.td_invoice_line_ids[:1].sale_order_currency_id
                or inv.env.company.currency_id
            )
            lines = inv.td_invoice_line_ids.filtered(lambda l: l.vat_type == "tax_included")
            if not lines:
                continue

            invoice_lines = lines.mapped("invoice_line_id").filtered(lambda l: l.move_id)
            source_total = False
            if invoice_lines:
                moves = invoice_lines.mapped("move_id")
                if len(moves) == 1:
                    source_total = currency.round(moves.amount_total)

            if source_total is False:
                sale_lines = lines.mapped("td_sale_order_line_id").filtered(lambda l: l.order_id)
                if sale_lines:
                    orders = sale_lines.mapped("order_id")
                    if len(orders) == 1:
                        source_total = currency.round(orders.amount_total)

            if source_total is False:
                continue

            current_total = currency.round(sum(lines.mapped("sum_price_with_vat")))
            delta = currency.round(source_total - current_total)
            if currency.is_zero(delta):
                continue

            last_line = lines[-1]
            last_line.sum_price_with_vat = currency.round(last_line.sum_price_with_vat + delta)
            last_line.sum_price_with_out_vat = currency.round(
                last_line.sum_price_with_out_vat + delta
            )
            last_line.sum_vat_price = currency.round(
                last_line.sum_price_with_vat - last_line.sum_price_with_out_vat
            )
            qty = last_line.quantity or last_line.invoice_quantity or last_line.sale_order_quantity or 0.0
            if qty:
                last_line.price_with_out_vat = currency.round(last_line.sum_price_with_out_vat / qty)
                last_line.vat_price = currency.round(last_line.sum_vat_price / qty)
            else:
                last_line.price_with_out_vat = 0.0
                last_line.vat_price = 0.0
