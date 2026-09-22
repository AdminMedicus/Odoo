# -*- coding: utf-8 -*-
from odoo import fields, models


class TdAgreement(models.Model):
    _inherit = 'td.agreement'

    td_lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        relation='td_agreement_stock_lot_rel',
        column1='agreement_id',
        column2='lot_id',
        string='Equipment Serial Number',
        help='Equipment this agreement covers. One customer may own several '
             'units and each unit has its own set of agreements.',
    )
