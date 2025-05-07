# -*- coding: utf-8 -*-

from odoo import models, fields


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
