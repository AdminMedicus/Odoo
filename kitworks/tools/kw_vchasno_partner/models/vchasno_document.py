import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class VchasnoDocument(models.Model):
    _inherit = 'kw.vchasno.document'

    partner_id = fields.Many2one(
        comodel_name='res.partner', )
