from odoo import api, models


class StockLotReport(models.Model):
    _inherit = 'stock.lot.report'

    @api.depends_context('td_equipment_display')
    def _compute_display_name(self):
        for record in self:
            if self.env.context.get('td_equipment_display'):
                record.display_name = record.product_id.display_name if record.product_id else record.lot_id.name
            else:
                record.display_name = record.lot_id.name
