from odoo import fields, models


class TdUKTZED(models.Model):
    _name = 'td.uktzed'
    _description = 'ToDo UKTZED'
    _rec_name = 'name'
    _parent_name = 'parent_id'

    name = fields.Char()
    code = fields.Char()
    title = fields.Char()
    visible = fields.Boolean(
        help='If True, you can see the list of '
             'all codes in the reference book '
             'when selecting codes in the item '
             'number or series/batch of goods',
        default=True
    )
    selectable = fields.Boolean(
        help='If True, you can see the list of '
             'all codes in the reference book '
             'when selecting codes in the item '
             'number or series/batch of goods',
        default=True
    )
    active = fields.Boolean(
        default=True
    )

    parent_id = fields.Many2one(
        comodel_name='td.uktzed',
        string='Parent',
        ondelete='cascade',
        index=True
    )
    child_ids = fields.One2many(
        comodel_name='td.uktzed',
        inverse_name='parent_id',
        string='Children'
    )
