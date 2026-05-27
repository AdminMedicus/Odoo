from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    td_is_goods_balance_of_act_res_st = fields.Boolean()
