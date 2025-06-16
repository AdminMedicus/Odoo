from odoo import fields, models, _


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    td_code_integration_one_c = fields.Integer(
        help=_('For integration with 1C')
    )
