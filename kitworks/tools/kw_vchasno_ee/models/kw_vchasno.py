import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class VchasnoDocument(models.Model):
    _inherit = 'kw.vchasno.document'

    dms_document_id = fields.Many2one(
        comodel_name='documents.document', readonly=True,)
    is_no_attach = fields.Boolean(
        default=False, readonly=True, )
    dms_file = fields.Binary(readonly=True)

    # pylint: disable=R1705
    def download_document(self):
        if self.dms_file and self.dms_document_id:
            att = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'documents.document'),
                ('res_id', '=', self.dms_document_id.id),
                ('res_field', '=', 'file')], limit=1)
            if att:
                base_url = self.env['ir.config_parameter'].get_param(
                    'web.base.url')
                url = '{}/web/content/{}?download=true'.format(
                    base_url, att.id)
                return {
                    "type": "ir.actions.act_url",
                    "url": url,
                    "target": "new", }
            else:
                return False
        else:
            return super().download_document()
