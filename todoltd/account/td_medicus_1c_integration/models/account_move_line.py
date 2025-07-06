from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    td_order_line_id = fields.Many2one(
        comodel_name='sale.order.line'
    )
    td_purchase_price = fields.Float()
    td_margin = fields.Float()
    td_margin_percent = fields.Float()