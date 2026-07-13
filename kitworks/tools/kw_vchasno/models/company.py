import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class Company(models.Model):
    _inherit = 'res.company'

    kw_vchasno_key_ids = fields.Many2many(
        comodel_name='kw.vchasno.key', string='Vchasno Key',
        compute='_compute_vchasno_key_ids', readonly=False, )

    def _compute_vchasno_key_ids(self):
        for obj in self:
            obj.kw_vchasno_key_ids = False
            obj.kw_vchasno_key_ids = self.env['kw.vchasno.key'].search(
                [('company_id', '=', obj.id)])
