from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_mrp_bom_id = fields.Many2one(
        comodel_name='mrp.bom',
        string='Related mrp bom',
        copy=False
    )
    td_bom_count = fields.Integer(compute='_compute_td_bom_count')
    td_completion_act_check = fields.Boolean(
        related="sale_order_template_id.td_completion_act_check",
        store=True
    )

    def _compute_td_bom_count(self):
        for rec in self:
            rec.td_bom_count = 1 if rec.td_mrp_bom_id else 0

    def action_open_td_bom(self):
        self.ensure_one()

        if not self.td_mrp_bom_id:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'BOM',
            'res_model': 'mrp.bom',
            'view_mode': 'form',
            'res_id': self.td_mrp_bom_id.id,
            'target': 'current',
        }

    def open_completion_act(self):
        self.ensure_one()

        bom_lines = []

        for line in self.order_line:
            if not line.product_template_id.product_variant_id:
                continue

            bom_lines.append((0, 0, {
                'product_id': line.product_template_id.product_variant_id.id,
                'product_qty': line.product_uom_qty,
                'product_uom_id': line.product_uom.id,
                'price_unit': line.price_unit
            }))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_product_tmpl_id': False,
                'default_type': 'phantom',
                'default_bom_line_ids': bom_lines,
                'default_td_sale_order_id': self.id,
            }
        }

    def action_confirm(self):
        self.ensure_one()

        if self.env.context.get('skip_wizard'):
            return super().action_confirm()

        if (
                not self.td_mrp_bom_id
                and self.sale_order_template_id
                and self.sale_order_template_id.td_completion_act_check
        ):
            return {
                'type': 'ir.actions.act_window',
                'name': 'Confirmation',
                'res_model': 'td.confirmation.bom.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_sale_order_id': self.id,
                }
            }

        return super().action_confirm()
