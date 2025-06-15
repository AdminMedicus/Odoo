from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    td_code_integration_one_c = fields.Integer()
