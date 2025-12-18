from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    td_date_commissioning = fields.Date(
        string='Date of Commissioning',
        help='Date when the product was put into operation.',
        tracking=True
    )

    # @api.model
    # def _get_invoice_in_picking_type_code(self):
    #     """Override to allow editing date_commissioning after confirmation."""
    #     return super()._get_invoice_in_picking_type_code()

    def write(self, vals):
        """Sync date_commissioning with related stock.picking."""
        res = super().write(vals)
        if 'td_date_commissioning' in vals:
            for move in self:
                # Find related pickings
                pickings = self.env['stock.picking'].search([
                    ('sale_id', '=', move.invoice_origin if move.move_type == 'out_invoice' else False)
                ])
                for picking in pickings:
                    if picking.td_date_commissioning != vals['td_date_commissioning']:
                        picking.td_date_commissioning = vals['td_date_commissioning']
        return res
