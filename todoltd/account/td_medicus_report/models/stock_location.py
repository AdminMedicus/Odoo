from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    td_condition_ids = fields.Many2many(
        comodel_name='td.stock.condition',
        string='Storage Conditions',
        help='Storage conditions associated with this stock location.'
    )