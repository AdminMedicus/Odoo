from odoo import models, fields, api, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def action_change_product_in_line(self):
        self.ensure_one()

        view_id = self.env.ref('td_contact_sale.td_change_product_in_sol_view_form').id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Change Product'),
            'res_model': 'td.change.product.in.sol',
            'view_mode': 'form',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'target': 'new',
            'context': {
                'default_td_sale_order_line': self.id,
            },
        }
