from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    td_manufacturer_directory_id = fields.Many2one(
        comodel_name='td.manufacturer.directory'
    )
    td_one_c_category_id = fields.Many2one(
        comodel_name='td.one_c.category'
    )
