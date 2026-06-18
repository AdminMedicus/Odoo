from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    td_manufacturer_directory_res_id = fields.Many2one(
        comodel_name='res.partner',
        string="Manufacturer",
    )

    standart_price = fields.Float(
        string="Lot Cost (standard)",
        digits="Product Price",
        help="Custom cost per lot/serial (used for GTD/import adjustments).",
        default=0.0,
    )

    standard_price = fields.Float(
        string="Lot Cost (standard)",
        related="standart_price",
        readonly=False,
        store=True,
        digits="Product Price",
        help="Compatibility alias for the correctly named lot cost field.",
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
        'quant_ids.quantity',
        'quant_ids.reserved_quantity',
        'quant_ids.location_id.usage',
        'quant_ids.company_id',
        'product_id.qty_available',
    )
    @api.depends_context('company', 'allowed_company_ids')
    def _compute_td_qty_fields(self):
        for lot in self:
            actual_qty = lot._td_get_internal_qty(company=lot.company_id)
            import_qty = lot._td_get_import_qty(company=lot.company_id)

            lot.product_qty = actual_qty + import_qty
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

    def _td_get_move_line_done_qty(self, move_line):
        if 'quantity' in move_line._fields:
            return move_line.quantity or 0.0

        if 'qty_done' in move_line._fields:
            return move_line.qty_done or 0.0

        return 0.0

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
            qty += abs(self._td_get_move_line_done_qty(line))
        return qty