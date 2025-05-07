from odoo import models, fields


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sub_client_id = fields.Many2one(
        comodel_name='res.partner',
    )
