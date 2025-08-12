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
        compute='_compute_td_customs_value_good'
    )
    td_taxes = fields.Float()
    td_taxes_price = fields.Float(
        compute='_compute_td_taxes_price',
        store=True
    )
    td_book_value = fields.Float()
    td_price_total = fields.Float(
        compute='_compute_td_price_total'
    )

    @api.depends('td_taxes')
    def _compute_td_taxes_price(self):
        for move in self:
            move.td_taxes_price = 0
            if move.td_taxes and move.td_price_unit:
                move.td_taxes_price = move.td_price_unit * move.td_taxes

    @api.depends('td_taxes_price', 'td_book_value', 'td_customs_value_good', 'td_currency_rate')
    def _compute_td_price_total(self):
        for move in self:
            move.td_price_total = move.td_book_value + move.td_taxes_price

    @api.depends('td_currency_rate', 'td_price_unit', 'product_id')
    def _compute_td_customs_value_good(self):
        for move in self:
            move.td_customs_value_good = 0
            if move.product_id and move.td_price_unit:
                if move.td_currency_rate:
                    move.td_customs_value_good = (
                        move.td_price_unit * move.td_currency_rate
                    )
                elif move.picking_id:
                    move.td_customs_value_good = (
                        move.td_price_unit * move.picking_id.td_currency_rate
                    )
