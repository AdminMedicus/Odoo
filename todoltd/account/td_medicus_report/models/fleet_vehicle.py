# -*- coding: utf-8 -*-
from odoo import fields, models


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    td_transport_ownership = fields.Selection(
        selection=[
            ('own', 'Own transport'),
            ('hired', 'Hired transport'),
        ],
        string='Ownership Type',
        default='own',
    )

    td_body_length = fields.Float(
        string='Body Length, m',
        digits=(16, 3),
    )
    td_body_width = fields.Float(
        string='Body Width, m',
        digits=(16, 3),
    )
    td_body_height = fields.Float(
        string='Body Height, m',
        digits=(16, 3),
    )
