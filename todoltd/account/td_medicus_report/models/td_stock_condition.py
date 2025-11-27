from odoo import _, api, fields, models


class TDStockCondition(models.Model):
    _name = 'td.stock.condition'

    name = fields.Char(string="Condition Name", required=True)
    description = fields.Text(string="Description")
