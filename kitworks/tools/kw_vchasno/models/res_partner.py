import logging

from odoo import models, fields


_logger = logging.getLogger(__name__)


class Partner(models.Model):
    _inherit = 'res.partner'

    vchasno_documents_ids = fields.One2many(
        comodel_name="kw.vchasno.document", inverse_name="contact_id")
