from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    td_is_warranty_applicable = fields.Boolean(
        string='Warranty',
        default=False,
        help='Indicates whether warranties can be applied to this product. Only available for products tracked by unique serial number.'
    )
    td_warranty_period_id = fields.Many2one(
        comodel_name='td.warranty.period',
        string='Warranty Period',
        compute="_td_compute_warranty_period",
        readonly=False,
        store=True,
        help='Warranty period for this product.'
    )
    td_is_extended_warranty = fields.Boolean(
        string='Is Extended Warranty',
        default=False,
        help='Indicates if this service is an extended warranty that can be sold separately.'
    )
    td_warranty_count = fields.Integer(
        string='Warranty Count',
        compute='_compute_td_warranty_count'
    )

    @api.depends('td_is_warranty_applicable')
    def _td_compute_warranty_period(self):
        """Auto-fill warranty period based on manufacturer and category.
        Only fills if there's exactly one match."""
        for product in self:
            if not product.td_is_warranty_applicable:
                product.td_warranty_period_id = False
                continue
                
            warranty_period = False
            if product.categ_id and product.td_manufacturer_directory_res_id:
                # Search for warranty periods matching both manufacturer and category
                domain = [
                    ('manufacturer', 'in', product.td_manufacturer_directory_res_id.id),
                    ('product_category', 'in', product.categ_id.id)
                ]
                periods = self.env['td.warranty.period'].search(domain)
                
                # Only auto-fill if there's exactly one match
                if len(periods) == 1:
                    warranty_period = periods
                    
            product.td_warranty_period_id = warranty_period

    def _compute_td_warranty_count(self):
        """Count warranties for products with serial numbers."""
        for product in self:
            if product.tracking == 'serial':
                warranty_count = self.env['td.warranty.record'].search_count([
                    ('product_id', '=', product.id)
                ])
                product.td_warranty_count = warranty_count
            else:
                product.td_warranty_count = 0

    @api.constrains('td_is_warranty_applicable', 'td_warranty_period_id')
    def _check_warranty_period_required(self):
        """Warranty period is required if warranty is applicable."""
        for product in self:
            if product.td_is_warranty_applicable and not product.td_warranty_period_id:
                raise ValidationError(
                    _('Warranty Period is required when Warranty is enabled.')
                )

    @api.onchange('tracking')
    def _onchange_tracking(self):
        """Reset warranty flag if tracking changes from serial."""
        if self.tracking != 'serial' and self.td_is_warranty_applicable:
            self.td_is_warranty_applicable = False
            self.td_warranty_period_id = False

    def action_view_warranties(self):
        """Open warranties view for this product."""
        self.ensure_one()
        action = self.env.ref('td_medicus_warranty.action_td_warranty_record').read()[0]
        action['domain'] = [('product_id', '=', self.id)]
        action['context'] = {
            'default_product_id': self.id,
        }
        return action
    