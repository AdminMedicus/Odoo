from odoo import fields, models


class TDManufacturerDirectory(models.Model):
    _name = 'td.manufacturer.directory'
    _description = 'TD Manufacturers directory'

    code = fields.Char()
    name = fields.Char()
    full_name = fields.Char()
    mark = fields.Boolean()
    non_resident = fields.Boolean()
    ukrainian_name = fields.Char()
