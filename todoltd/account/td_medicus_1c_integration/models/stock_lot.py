from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    standart_price = fields.Float(
        string="TD Lot Cost (standard)",
        digits="Product Price",
        help="Custom cost per lot/serial (used for GTD/import adjustments).",
        default=0.0,
    )

    product_qty = fields.Float(
        compute='_compute_td_qty_fields',
        string='Quantity',
        digits='Product Unit of Measure',
    )

    td_available_qty = fields.Float(
        string='Available Quantity',
        compute='_compute_td_qty_fields',
        digits='Product Unit of Measure',
    )

    @api.depends(
        'product_id',
        'company_id',
        'product_id.qty_available',
    )
    def _compute_td_qty_fields(self):
        for lot in self:
            actual_qty = lot._td_get_internal_qty(company=lot.company_id)
            import_qty = lot._td_get_import_qty(company=lot.company_id)

            # Базове поле показує весь on hand + заблокований імпорт
            lot.product_qty = actual_qty + import_qty

            # Нове поле тільки доступну кількість без import
            lot.td_available_qty = actual_qty

    def _td_get_internal_qty(self, company=None):
        self.ensure_one()
        Quant = self.env["stock.quant"].sudo()

        domain = [
            ("lot_id", "=", self.id),
            ("product_id", "=", self.product_id.id),
            ("location_id.usage", "=", "internal"),
        ]

        company_id = company.id if company else (self.company_id.id if self.company_id else False)
        if company_id:
            domain.append(("company_id", "in", [company_id, False]))

        quants = Quant.search(domain)
        return sum(quants.mapped("quantity"))

    def _td_get_import_qty(self, company=None):
        self.ensure_one()
        MoveLine = self.env['stock.move.line'].sudo()

        domain = [
            ('lot_id', '=', self.id),
            ('product_id', '=', self.product_id.id),
            ('picking_id.state', '=', 'import'),
            ('picking_id.picking_type_code', '=', 'incoming'),
            ('location_dest_id.usage', '=', 'internal'),
        ]

        company_id = company.id if company else (self.company_id.id if self.company_id else False)
        if company_id:
            domain.append(('company_id', 'in', [company_id, False]))

        move_lines = MoveLine.search(domain)

        qty = 0.0
        for line in move_lines:
            qty += abs(line.qty_done or line.quantity or 0.0)
        return qty