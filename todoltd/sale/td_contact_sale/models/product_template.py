import logging
from odoo import fields, models, api, _

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    td_product_template_ids = fields.Many2many(
        comodel_name='product.template',
        relation = 'td_product_template_rel',
        column1 = 'template_id',
        column2 = 'related_template_id',
    )

    def action_choose_product_for_sol(self):
        self.ensure_one()
        sale_order_line_id = self.env.context.get('active_id')
        if sale_order_line_id:
            sale_order_line = self.env['sale.order.line'].browse(sale_order_line_id)
            product = self.env['product.product'].search([
                ('product_tmpl_id', '=', self.id)
            ], limit=1)
            if product:
                sale_order_line.write({'product_id': product.id})
        return {'type': 'ir.actions.act_window_close'}
