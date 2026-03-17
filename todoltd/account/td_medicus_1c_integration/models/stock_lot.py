from odoo import fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    standart_price = fields.Float(
        string="Lot Cost (standard)",
        digits="Product Price",
        help="Custom cost per lot/serial (used for GTD/import adjustments).",
        default=0.0,
    )

    def _td_get_internal_qty(self, company=None):
        """Return qty on hand for this lot in internal locations.
        If lot.company_id is empty, we still must count company quants (common in many DBs).
        """
        self.ensure_one()
        Quant = self.env["stock.quant"].sudo()

        domain = [
            ("lot_id", "=", self.id),
            ("product_id", "=", self.product_id.id),
            ("location_id.usage", "=", "internal"),
        ]

        company_id = (company.id if company else (self.company_id.id if self.company_id else False))
        if company_id:
            domain.append(("company_id", "in", [company_id, False]))

        quants = Quant.search(domain)
        return sum(quants.mapped("quantity"))
