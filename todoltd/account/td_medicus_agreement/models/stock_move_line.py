from odoo import models, fields, api


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    td_uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed',
        compute='_compute_product_id_and_lot_ids',
        readonly=False
    )

    @api.onchange('lot_id', 'move_id.product_id')
    def _compute_product_id_and_lot_ids(self):
        for line in self:
            product = line.product_id
            if line.lot_id:
                line.td_uktzed_code_id = (
                        line.lot_id.td_uktzed_code_id.id or False
                )
            if not line.td_uktzed_code_id:
                if product.td_uktzed_code_id:
                    line.td_uktzed_code_id = product.td_uktzed_code_id.id
                else:
                    line.td_uktzed_code_id = False

    @api.onchange('td_uktzed_code_id')
    def _onchange_td_uktzed_code_id(self):
        for line in self:
            if line.lot_id:
                line.lot_id.browse(line.lot_id._origin.id).td_uktzed_code_id = line.td_uktzed_code_id.id
