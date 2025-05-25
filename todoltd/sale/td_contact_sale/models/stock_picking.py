from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sub_client_id = fields.Many2one(
        comodel_name='res.partner',
    )

    allowed_sub_client_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='stock_picking_allowed_sub_client_rel',
        column1='stock_picking_id',
        column2='allowed_sub_client_id',
    )

    def button_validate(self):
        res = super().button_validate()
        picking_ids = self.move_ids.move_dest_ids.picking_id
        for picking in picking_ids:
            picking.sub_client_id = self.sub_client_id.id

        if self.picking_type_code == 'internal':
            self.sale_id.stock_button_active = False
        return res

    @api.onchange('partner_id')
    def _onchange_domain_for_sub_client_id(self):
        for res in self:
            if res.partner_id:
                res.allowed_sub_client_ids = (
                    res.partner_id.sub_client_rel_ids.sub_client_id.ids
                    or False
                )
                typical = res.partner_id.sub_client_rel_ids.filtered(
                    lambda rec: rec.is_typical
                )
                if typical:
                    res.sub_client_id = typical.sub_client_id.id
                else:
                    res.sub_client_id = False
            else:
                res.allowed_sub_client_ids = False
                res.sub_client_id = False
