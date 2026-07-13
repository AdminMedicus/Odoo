import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class QualityList(models.Model):
    _name = 'kw.vchasno.status'
    _description = 'Vchasno Status Document'

    name = fields.Char(readonly=True, )
    status_ref = fields.Char(readonly=True, )


class DeliveryTypeList(models.Model):
    _name = 'kw.vchasno.category'
    _description = 'Vchasno Category Document'

    name = fields.Char(readonly=True, )
    category_ref = fields.Char(readonly=True, )
