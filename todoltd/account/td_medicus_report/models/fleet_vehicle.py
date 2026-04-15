# -*- coding: utf-8 -*-
from odoo import fields, models, api, _


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

    @api.depends('model_id.brand_id.name', 'model_id.name', 'license_plate')
    def _compute_vehicle_name(self):
        for record in self:
            record.name = (record.model_id.brand_id.name or '') + '/' + (record.model_id.name or '')
