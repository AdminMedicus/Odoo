from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    td_sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Related commercial offer'
    )
    td_sale_order_count = fields.Integer(
        compute='_td_compute_sale_order_count'
    )
    td_order_date = fields.Date(
        string='Date'
    )
    td_order_number = fields.Integer(
        string='Number'
    )
    td_head_commission = fields.Many2one(
        comodel_name='hr.employee',
        string='Head of commission'
    )
    td_commission_members = fields.Many2many(
        comodel_name='hr.employee',
        string='Commission members'
    )
    td_approval = fields.Many2one(
        comodel_name='hr.employee',
        string='Approval'
    )

    def _td_compute_sale_order_count(self):
        for rec in self:
            rec.td_sale_order_count = 1 if rec.td_sale_order_id else 0

    def action_open_td_sale_order(self):
        self.ensure_one()

        if not self.td_sale_order_id:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sale Order',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.td_sale_order_id.id,
            'target': 'current',
        }

    def action_create_production_order(self):
        self.ensure_one()

        if not self.product_tmpl_id:
            raise UserError(_("The main product is not listed in the specification."))
        price = 0
        description = ''
        for bom_line in self.bom_line_ids:
            price += bom_line.product_qty * bom_line.price_unit
            description += bom_line.display_name + '\n'

        self.product_tmpl_id.write({
            'list_price': price,
            'description_sale': description
        })
        product = self.product_id or self.product_tmpl_id.product_variant_id

        production = self.env['mrp.production'].create([{
            'product_id': product.id,
            'product_qty': self.product_qty or 1.0,
            'bom_id': self.id,
            'user_id': self.env.user.id,
            'date_start': fields.Datetime.now(),
        }])

        production.action_confirm()
        if self.td_sale_order_id:
            sale_order = self.td_sale_order_id

            sale_order.write({
                'td_mrp_bom_id': self.id,
            })

            sale_order.order_line.unlink()

            sale_order.write({
                'order_line': [(0, 0, {
                    'product_id': self.product_tmpl_id.product_variant_id.id,
                    'product_uom_qty': 1,
                    'name': self.product_tmpl_id.name,
                })]
            })
        if not self.td_sale_order_id:
            raise UserError(_('You cannot create a picking document because a sales order is not specified.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.td_sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
