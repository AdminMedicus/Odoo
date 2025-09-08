from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockWareHouse(models.Model):
    _inherit = "stock.warehouse"

    td_is_warehouse_for_sale_order = fields.Boolean()

    @api.onchange('td_is_warehouse_for_sale_order')
    def _onchange_is_warehouse_for_sale_order(self):
        for rec in self:
            if rec.td_is_warehouse_for_sale_order:
                records = self.search([
                    ('td_is_warehouse_for_sale_order', '=', True)
                ])
                if len(records) > 0:
                    raise ValidationError(_("You active sum WareHouse for SaleOrder"))
