from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_view_warranties(self):
        """Open warranties view for this product."""
        self.ensure_one()
        action = self.env.ref('td_medicus_warranty.action_td_warranty_record').read()[0]
        action['domain'] = [('product_id', '=', self.product_tmpl_id.id)]
        action['context'] = {
            'default_product_id': self.product_tmpl_id.id,
        }
        return action
