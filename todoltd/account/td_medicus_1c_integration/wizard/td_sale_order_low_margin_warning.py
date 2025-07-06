from odoo import models, api

class SaleOrderLowMarginWarning(models.TransientModel):
    _name = 'td.sale.order.low.margin.warning'
    _description = 'Warning: Price is lower than cost'

    def action_continue(self):
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        return sale_order.with_context(force_confirm_low_margin=True).action_confirm()

    def action_back_to_edit(self):
        return {'type': 'ir.actions.act_window_close'}
