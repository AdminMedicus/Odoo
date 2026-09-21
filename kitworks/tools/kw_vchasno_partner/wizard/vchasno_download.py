import logging

from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class VchasnoDownloadDocumentWizard(models.TransientModel):
    _inherit = 'vchasno.download.document.wizard'

    is_partner_recipient = fields.Boolean(
        default=False, )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        domain="[('kw_is_vchasno', '=', True), ]")

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        for obj in self:
            if obj.partner_id:
                obj.edrpou_recipient = obj.partner_id.vat
                obj.email_recipient = obj.partner_id.email

    def write_vchasno_params(self, document_id):
        res = super().write_vchasno_params(document_id)
        if document_id:
            document_id.write({'partner_id': self.partner_id.id})
        return res
