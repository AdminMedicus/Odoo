from odoo import models, fields, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    td_invoice_id = fields.Many2one(
        comodel_name='account.move.line'
    )
