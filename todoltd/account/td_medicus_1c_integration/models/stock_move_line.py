from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    td_manufacturer_directory_res_id = fields.Many2one(
        comodel_name='res.partner',
        string="Manufacturer",
        # compute='_compute_td_manufacturer_directory_res_id',
        # store=True,
        # readonly=False,
    )

    @api.onchange('product_id', 'lot_id', 'lot_id.td_manufacturer_directory_res_id', 'quant_id')
    def _compute_td_manufacturer_directory_res_id(self):
        for line in self:
            if lot := line.quant_id.lot_id:
                line.td_manufacturer_directory_res_id = lot.td_manufacturer_directory_res_id
            else:
                line.td_manufacturer_directory_res_id = line.product_id.td_manufacturer_directory_res_id

    def _prepare_new_lot_vals(self):
        vals = super()._prepare_new_lot_vals()
        if self.td_manufacturer_directory_res_id:
            vals['td_manufacturer_directory_res_id'] = self.td_manufacturer_directory_res_id.id
        return vals

    def _td_sync_manufacturer_to_lot(self):
        for line in self:
            if (
                line.lot_id
                and line.td_manufacturer_directory_res_id
                and not line.lot_id.td_manufacturer_directory_res_id
            ):
                line.lot_id.td_manufacturer_directory_res_id = line.td_manufacturer_directory_res_id

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._td_sync_manufacturer_to_lot()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'td_manufacturer_directory_res_id' in vals or 'lot_id' in vals:
            self._td_sync_manufacturer_to_lot()
        return res
