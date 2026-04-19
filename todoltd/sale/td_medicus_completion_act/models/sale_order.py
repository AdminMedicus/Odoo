from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def open_completion_act(self):
        self.ensure_one()

        bom_lines = []

        for line in self.order_line:
            if not line.product_template_id.product_variant_id:
                continue

            bom_lines.append((0, 0, {
                'product_id': line.product_template_id.product_variant_id.id,
                'product_qty': line.product_uom_qty,
                'product_uom_id': line.product_uom.id
            }))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_product_tmpl_id': False,
                'default_type': 'normal',
                'default_bom_line_ids': bom_lines,
                'default_td_sale_order_id': self.id,
            }
        }
