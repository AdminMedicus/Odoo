from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    td_product_conditions = fields.Char(
        string='Storage / Transportation Conditions'
    )
    