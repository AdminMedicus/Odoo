from odoo import fields, models, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    td_currency_rate = fields.Float(
        string="Currency Rate",
        digits=(12, 6),
        # related="picking_id.td_currency_rate"
    )
    td_customs_rate = fields.Float()


    td_customs_value_good = fields.Float(
        compute='_compute_td_customs_value_good',
        store=True
    )
    td_taxes_ids = fields.Many2many(
        comodel_name='account.tax',
        related='product_id.taxes_id'
    )
    td_taxes = fields.Float()
    td_taxes_price = fields.Float(
        compute='_compute_td_taxes_price',
        store=True
    )
    td_book_value = fields.Float()
    td_price_total = fields.Float(
        compute='_compute_td_price_total',
        store=True
    )

    td_lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        compute='_compute_td_lot_ids'
    )

    @api.depends('lot_ids', 'move_line_ids', 'move_line_ids.quant_id')
    def _compute_td_lot_ids(self):
        for rec in self:
            lots = []
            for move_line in rec.move_line_ids:
                if move_line.quant_id and move_line.quant_id.lot_id:
                    lots.append(move_line.quant_id.lot_id.id)
                elif move_line.lot_id:
                    lots.append(move_line.lot_id.id)
            rec.td_lot_ids = [(6, 0, lots)]

    @api.depends('td_taxes', 'td_taxes_ids')
    def _compute_td_taxes_price(self):
        for move in self:
            is_import = move.picking_id.td_is_import if move.picking_id else False
            current_line = False
            if move.sale_line_id:
                current_line = move.sale_line_id
            elif move.purchase_line_id:
                current_line = move.purchase_line_id

            if not is_import:
                move.td_taxes = move.td_taxes_ids[0].amount / 100 if move.td_taxes_ids else 0

            move.td_taxes_price = 0
            if current_line and not is_import:
                move.td_taxes_price = current_line.price_tax

            if move.td_taxes and move.td_price_unit and is_import:
                move.td_taxes_price = move.td_customs_value_good * move.td_taxes
                # move.td_taxes_price = move.td_price_subtotal * move.td_taxes
                # if is_import:
                #     move.td_taxes_price = move.td_customs_value_good * move.td_taxes

    @api.depends('td_taxes_price', 'td_book_value', 'td_customs_value_good', 'td_currency_rate')
    def _compute_td_price_total(self):
        for move in self:
            current_line = False
            if move.sale_line_id:
                current_line = move.sale_line_id
            elif move.purchase_line_id:
                current_line = move.purchase_line_id

            if move.picking_id.td_is_import:
                move.td_price_total = move.td_book_value + move.td_taxes_price
            else:
                move.td_price_total = current_line.price_total if current_line else 0.0
                # move.td_price_total = move.td_price_subtotal + move.td_taxes_price

    @api.depends('td_currency_rate', 'td_price_unit', 'product_id', 'picking_id.td_currency_rate')
    def _compute_td_customs_value_good(self):
        for move in self:
            rate = move.td_currency_rate or (move.picking_id and move.picking_id.td_currency_rate) or 0.0

            if move.product_id and move.td_price_unit:
                move.td_customs_value_good = move.td_price_unit * rate
            else:
                move.td_customs_value_good = 0.0
