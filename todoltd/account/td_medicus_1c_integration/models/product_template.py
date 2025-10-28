from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    td_manufacturer_directory_id = fields.Many2one(
        comodel_name='td.manufacturer.directory'
    )
    td_manufacturer_directory_res_id = fields.Many2one(
        comodel_name='res.partner'
    )
    td_one_c_category_id = fields.Many2one(
        comodel_name='td.one_c.category'
    )
