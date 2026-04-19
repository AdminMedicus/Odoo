from odoo import api, models


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.depends(
        "td_taxes",
        "td_taxes_ids",
        "quantity",
        "td_price_unit",
        "td_untaxed_price_unit",
        "sale_line_id.tax_id",
        "sale_line_id.price_unit",
        "sale_line_id.discount",
        "sale_line_id.order_id.partner_id",
        "sale_line_id.order_id.partner_shipping_id",
        "sale_line_id.order_id.currency_id",
        "purchase_line_id.taxes_id",
        "purchase_line_id.price_unit",
        "purchase_line_id.order_id.partner_id",
        "purchase_line_id.order_id.currency_id",
        "product_id",
        "picking_id.partner_id",
        "picking_id.td_is_import",
    )
    def _compute_td_taxes_price(self):
        for move in self:
            is_import = move.picking_id.td_is_import if move.picking_id else False

            sale_line = move.sale_line_id
            purchase_line = move.purchase_line_id

            taxes = self.env["account.tax"]
            currency = move.company_id.currency_id
            partner = move.picking_id.partner_id
            price_unit = move.td_price_unit or 0.0
            quantity = move.quantity or 0.0

            if sale_line:
                taxes = sale_line.tax_id
                currency = sale_line.currency_id or sale_line.order_id.currency_id or move.company_id.currency_id
                partner = sale_line.order_id.partner_shipping_id or sale_line.order_id.partner_id
                price_unit = sale_line.price_unit * (1.0 - (sale_line.discount or 0.0) / 100.0)
            elif purchase_line:
                taxes = purchase_line.taxes_id
                currency = purchase_line.currency_id or purchase_line.order_id.currency_id or move.company_id.currency_id
                partner = purchase_line.order_id.partner_id
                price_unit = purchase_line.price_unit
            else:
                taxes = move.td_taxes_ids

            if not is_import:
                percent_taxes = taxes.filtered(lambda tax: tax.amount_type == "percent")
                move.td_taxes = sum(percent_taxes.mapped("amount")) / 100 if percent_taxes else 0.0

            move.td_taxes_price = 0.0

            if taxes and quantity and not is_import:
                taxes_res = taxes.compute_all(
                    price_unit,
                    currency=currency,
                    quantity=quantity,
                    product=move.product_id,
                    partner=partner,
                )
                move.td_taxes_price = taxes_res["total_included"] - taxes_res["total_excluded"]

            elif move.td_taxes and move.td_price_unit and is_import:
                move.td_taxes_price = move.td_customs_value_good * move.td_taxes
