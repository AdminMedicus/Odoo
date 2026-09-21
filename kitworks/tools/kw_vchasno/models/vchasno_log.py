import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class VchasnoLog(models.Model):
    _name = 'kw.vchasno.log'
    _description = 'Vchasno log'

    name = fields.Char(
        string='URL', )
    json = fields.Text()
    params = fields.Text()
    headers = fields.Text()
    error = fields.Text()
    response = fields.Text()
    method = fields.Char()
    code = fields.Char()
    token = fields.Char()
    is_download = fields.Boolean(
        default=False, )
