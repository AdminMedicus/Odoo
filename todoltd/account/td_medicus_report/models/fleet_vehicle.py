# -*- coding: utf-8 -*-
from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    td_transport_ownership = fields.Selection(
        selection=[
            ('own', 'Власний транспорт'),
            ('hired', 'Найм'),
        ],
        string='Власність',
        default='own',
    )

    td_body_length = fields.Float(
        string='Довжина кузова, м',
        digits=(16, 3),
    )
    td_body_width = fields.Float(
        string='Ширина кузова, м',
        digits=(16, 3),
    )
    td_body_height = fields.Float(
        string='Висота кузова, м',
        digits=(16, 3),
    )
