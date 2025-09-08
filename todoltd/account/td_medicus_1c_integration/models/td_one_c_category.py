from odoo import fields, models


class TDCategoryOneC(models.Model):
    _name = 'td.one_c.category'
    _description = '1C Categories'

    name = fields.Char(
        string='Category Name'
    )
    parent_id = fields.Many2one(
        comodel_name='td.one_c.category'
    )
    code = fields.Char()
    child_ids = fields.One2many(
        comodel_name='td.one_c.category',
        inverse_name='parent_id'
    )
