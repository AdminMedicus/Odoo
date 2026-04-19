from odoo import fields, models


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    price_unit = fields.Float(
        string='Price Unit'
    )
