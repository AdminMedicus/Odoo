from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    td_type_of_trade = fields.Selection(
        [
            ('prepayment_credit', 'Prepayment | Credit'),
            ('res_storage', 'Responsible Storage'),
        ], default=False,
    )

    @api.onchange('td_type_of_trade')
    def _onchange_td_type_of_trade(self):
        for pick_type in self:
            if pick_type.td_type_of_trade:
                rec = self.search([('td_type_of_trade', '=', pick_type.td_type_of_trade)])
                if rec and len(rec) > 1:
                    raise ValidationError(_("You can use this state only for 1 Picking Type"))
