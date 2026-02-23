from odoo import _, fields, models
from odoo.exceptions import UserError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    td_sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Related commercial offer'
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

    def action_create_production_order(self):
        self.ensure_one()

        if not self.product_tmpl_id:
            raise UserError(_("The main product is not listed in the specification."))

        product = self.product_id or self.product_tmpl_id.product_variant_id

        production = self.env['mrp.production'].create([{
            'product_id': product.id,
            'product_qty': self.product_qty or 1.0,
            'bom_id': self.id,
            'user_id': self.env.user.id,
            'date_start': fields.Datetime.now(),
        }])

        production.action_confirm()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Picking created'),
                'message': _('Name: {name}').format(name=production.name),
                'type': 'success',
            }
        }
