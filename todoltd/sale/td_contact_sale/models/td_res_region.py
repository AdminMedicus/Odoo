# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ToDoCountryRegion(models.Model):
    _name = 'td.res.country.region'
    _description = 'Country Region'

    name = fields.Char(
        string='Region Name'
    )
    parent_region_id = fields.Many2one(
        comodel_name='td.res.country.region',
        string='Parent Region'
    )
    child_region_ids = fields.One2many(
        comodel_name='td.res.country.region',
        inverse_name='parent_region_id',
        string='Child Regions'
    )

    @api.model
    @api.readonly
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = list(args or [])
        if self.env.context.get('region_leaf_only'):
            args += [('child_region_ids', '=', False)]
        return super(ToDoCountryRegion, self).name_search(name=name, args=args, operator=operator, limit=limit)