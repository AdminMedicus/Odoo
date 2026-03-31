from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TdWarrantyPeriod(models.Model):
    _name = 'td.warranty.period'
    _description = 'Warranty Period'

    name = fields.Char(string='Warranty Name', required=True)
    manufacturer = fields.Many2many(
        comodel_name='res.partner',
        string='Manufacturers'
    )
    product_category = fields.Many2many(
        comodel_name='product.category',
        string='Product Categories'
    )
    duration_months = fields.Integer(string='Duration (Months)', required=True)
    description = fields.Text(string='Description')


    @api.constrains('manufacturer', 'product_category')
    def _check_unique_manufacturer_category(self):
        for record in self:
            if record.manufacturer and record.product_category:
                duplicate = self.search([
                    ('id', '!=', record.id),
                ])
                for dup in duplicate:
                    if (set(dup.manufacturer.ids) == set(record.manufacturer.ids) and
                        set(dup.product_category.ids) == set(record.product_category.ids)):
                        raise ValidationError(
                            _('A warranty period with this combination of manufacturers and product categories already exists!')
                        )
