from odoo import fields, models, api


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

    @api.model
    @api.readonly
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = list(args or [])
        if self.env.context.get('category_leaf_only'):
            args += [('child_ids', '=', False)]
        return super(TDCategoryOneC, self).name_search(name=name, args=args, operator=operator, limit=limit)
