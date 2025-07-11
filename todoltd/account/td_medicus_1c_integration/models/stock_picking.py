from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        if self and self.id:
            for picking in self:
                for move in picking.move_ids:
                    for lot in move.lot_ids:
                        uktzed_line = move.move_line_ids.filtered(lambda lin: lin.lot_id.id == lot.id)
                        move.lot_ids.write({
                            'td_uktzed_code_id': uktzed_line.td_uktzed_code_id.id if uktzed_line else False
                        })
                        move.td_uktzed_code_id = uktzed_line.td_uktzed_code_id.id if uktzed_line else False
        return res
