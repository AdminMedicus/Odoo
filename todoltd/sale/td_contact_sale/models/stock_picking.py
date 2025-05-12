from odoo import models, fields


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sub_client_id = fields.Many2one(
        comodel_name='res.partner',
    )

    def button_validate(self):
        res = super().button_validate()
        picking_ids = self.move_ids.move_dest_ids.picking_id
        for picking in picking_ids:
            picking.sub_client_id = self.sub_client_id.id

        if self.picking_type_code == 'internal':
            self.sale_id.stock_button_active = False
        return res
