import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    kw_is_vchasno = fields.Boolean(
        default=False, )
