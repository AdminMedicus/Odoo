# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    records = env['stock.picking'].search([
        ('td_ttn_gross_weight', '!=', False)
    ])

    records.write({
        'td_ttn_gross_weight': False
    })
