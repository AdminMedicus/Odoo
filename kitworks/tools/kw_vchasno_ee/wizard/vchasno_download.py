import logging

from odoo import fields, models, exceptions, _

_logger = logging.getLogger(__name__)


class VchasnoDownloadDocumentWizard(models.TransientModel):
    _inherit = 'vchasno.download.document.wizard'

    dms_document_id = fields.Many2one(
        comodel_name='documents.document', )
    is_no_attach = fields.Boolean(
        default=False, readonly=True, )
    is_dms = fields.Boolean(
        default=False, )
    filename = fields.Char()

    def write_vchasno_params(self, document_id):
        res = super().write_vchasno_params(document_id)
        if document_id and self.dms_document_id:
            self.dms_document_id.write({
                'vchasno_document_id': document_id.id,
                'vchasno_id': document_id.vchasno_id.id, })
        return res

    def add_document(self):
        if self.is_dms and self.is_no_attach:
            vchasno_api = self.vchasno_id.vchasno_api()
            doc = vchasno_api.post_document(
                file=self.file,
                filename=self.filename,
                category=self.category,
                doc_number=self.number,
                amount=int(self.amount * 100),
                recipient_edrpou=self.edrpou_recipient,
                recipient_emails=self.email_recipient, )
            if doc:
                vchasno_document = self.env['kw.vchasno.document']
                for vals in doc['documents']:
                    vchasno_document_id = vchasno_document.updates_document(
                        vals)
                    vchasno_document_id.write(
                        {'document_id': self.dms_document_id.id,
                         'is_no_attach': self.is_no_attach,
                         'vchasno_id': self.vchasno_id.id,
                         'edrpou_owner': self.edrpou_owner,
                         'email_owner': self.vchasno_id.email_owner,
                         'company_name_owner': self.vchasno_id.name,
                         'edrpou_recipient': self.edrpou_recipient,
                         'dms_file': self.file if self.file else None,
                         'email_recipient': self.email_recipient, })
                    self.write_vchasno_params(vchasno_document_id)
                    return vchasno_document_id
            else:
                raise exceptions.ValidationError(
                    _('The document is not loaded into the system'))
        else:
            return super().add_document()
