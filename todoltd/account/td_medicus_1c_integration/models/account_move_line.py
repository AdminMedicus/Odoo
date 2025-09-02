from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    td_order_line_id = fields.Many2one(
        comodel_name='sale.order.line'
    )
    td_purchase_price = fields.Float(
        compute='_compute_td_purchase_margin'
    )
    td_margin = fields.Float(
        compute='_compute_td_purchase_margin'
    )
    td_margin_percent = fields.Float(
        compute='_compute_td_purchase_margin'
    )
    td_paid_price = fields.Float()

    @api.depends('td_order_line_id', 'product_id')
    def _compute_td_purchase_margin(self):
        for line in self:
            if line.move_id.td_advance_payment_method == 'delivered':
                records = self.env['stock.move'].search([
                    ('sale_line_id', '=', line.td_order_line_id.id)
                ])
                outgoing_record = records.filtered(
                    lambda l: l.picking_id
                              and l.picking_id.picking_type_code == 'outgoing'
                              and l.picking_id.state == 'done'
                )
                if outgoing_record:
                    purchase_price = [lot.standard_price for lot in outgoing_record[0].lot_ids]
                    if purchase_price:
                        line.td_purchase_price = purchase_price[0]
                    else:
                        line.td_purchase_price = line.product_id.standard_price
                else:
                    line.td_purchase_price = line.product_id.standard_price
            else:
                line.td_purchase_price = line.product_id.standard_price

            line.td_margin = (line.price_unit - line.td_purchase_price) * line.quantity

            if line.price_unit:
                line.td_margin_percent = line.td_margin / (line.price_unit / 100)
            else:
                line.td_margin_percent = 0
