from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    td_date_commissioning = fields.Date(
        string='Date of Commissioning',
        help='Date when the product was put into operation.',
        tracking=True
    )

    def write(self, vals):
        """Sync date_commissioning with related stock.picking."""
        res = super().write(vals)
        if 'td_date_commissioning' in vals:
            for move in self:
                order = move.td_order_id
                if order and order.td_date_commissioning != vals['td_date_commissioning']:
                    order.td_date_commissioning = vals['td_date_commissioning']

                pickings = order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing'
                )
                for picking in pickings:
                    if picking.td_date_commissioning != vals['td_date_commissioning']:
                        picking.td_date_commissioning = vals['td_date_commissioning']
        return res
