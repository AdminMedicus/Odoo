from odoo import fields, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    td_uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed'
    )