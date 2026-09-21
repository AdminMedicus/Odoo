import os
import logging

from odoo import fields, models, api, exceptions, _

_logger = logging.getLogger(__name__)


class VchasnoDownloadDocumentWizard(models.TransientModel):
    _name = 'vchasno.download.document.wizard'
    _description = 'vchasno.download.document.wizard'

    _vchasno_format = [
        ('pdf', 'PDF'),
        ('jpeg', 'JPEG'),
        ('xml', 'XML'),
        ('dbf', 'DBF'),
        ('txt', 'TXT'),
        ('png', 'PNG'),
        ('zip', 'ZIP'),
        ('docx', 'DOCX'),
        ('xlsx', 'XLSX'), ]

    def _default_key(self):
        return self.env['kw.vchasno.key'].search(
            [('company_id', '=', self.env.user.company_id.id),
             ('user_id', '=', self.env.user.id), ], limit=1)

    def _get_selection_category(self):
        selection_category = []
        category_ids = self.env['kw.vchasno.category'].search([])
        for category in category_ids:
            selection_category.append((category.category_ref, category.name))
        return selection_category

    contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contact',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.user.company_id,
    )
    vchasno_id = fields.Many2one(
        comodel_name='kw.vchasno.key',
        required=True,
        domain="[('company_id','=',company_id)]",
        default=lambda self: self._default_key(),
    )
    file = fields.Binary()

    edrpou_owner = fields.Char(
        help='ЄДРПОУ/ІПН власника документу',
        required=True,
    )
    edrpou_recipient = fields.Char(
        help='ЄДРПОУ/ІПН отримувача документу/контрагента',
        required=True,
    )
    date = fields.Date(
        help='Дата формування документу',
        default=fields.Date.today,
        readonly=True,
    )
    type = fields.Char(
        help='Тип документу',
        required=True,
    )
    number = fields.Char(
        help='Порядковий номер документу',
        required=True,
    )
    email_recipient = fields.Char(
        help='Email отримувача документу, або декілька, записані через кому.',
    )
    amount = fields.Float(
        default=0,
    )
    is_internal = fields.Boolean(
        help='Чи є внутрішнім документом',
        default=False,
    )
    ir_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='Attachment',
    )
    format = fields.Selection(
        selection=_vchasno_format,
        default='pdf',
        required=True,
    )
    category = fields.Selection(
        selection='_get_selection_category',
        default='0',
        ondelete={'0': 'set default'},
    )
    owner_signatire_count = fields.Integer(
        string='Signatures Owner',
        help='Number of owner signatures required.',
        default=1,
    )
    recipient_signatire_count = fields.Integer(
        string='Signatures Recipient',
        help='Number of recipient signatures required.',
        default=1,
    )
    first_sign_by = fields.Selection(
        selection=[
            ("owner", "Owner"),
            ("recipient", "Recipient"),
        ],
        default="recipient",
        ondelete={"recipient": "set default"},
        help='Defines who should sign the document first.',
    )
    send_immediately = fields.Boolean(
        help='Check to send the document to the recipient immediately. '
        'Readonly if no Email Recipient or first_sign_by = "Owner".',
    )

    @api.onchange('first_sign_by', 'email_recipient')
    def onchange_send_immediately_params(self):
        for obj in self:
            if obj.first_sign_by == 'owner' or not obj.email_recipient:
                obj.send_immediately = False

    @api.onchange('vchasno_id')
    def onchange_vchasno_id(self):
        for obj in self:
            if obj.vchasno_id:
                obj.edrpou_owner = obj.vchasno_id.edrpou_owner

    @api.onchange('contact_id', 'vchasno_id')
    def onchange_contact_id(self):
        for obj in self:
            obj.edrpou_recipient = False
            obj.email_recipient = False
            if obj.contact_id and obj.vchasno_id \
                    and obj.vchasno_id.field_contact_info_id:
                obj.edrpou_recipient = \
                    obj.contact_id[obj.vchasno_id.field_contact_info_id.name]
                obj.email_recipient = obj.contact_id.email

    def write_vchasno_params(self, document_id):
        return document_id

    def add_document(self):
        vchasno_api = self.vchasno_id.vchasno_api()
        date = str(self.date).replace('-', '')
        emails = ','.join(
            [email.strip() for email in self.email_recipient.split(',')]
        )
        cleared_name = os.path.splitext(self.number)[0].replace('_', '-')
        vchasno_file_name = '{}_{}_{}_{}_{}_{}.{}'.format(
            self.edrpou_owner,
            self.edrpou_recipient,
            date,
            self.type,
            cleared_name,
            emails,
            self.format,
        )
        attachment = self.ir_attachment_id
        if not self.ir_attachment_id:
            attachment = self.env['ir.attachment'].create({
                'datas': self.file,
                'name': self.number,
            })
        res = vchasno_api.post_document(
            file=attachment.datas,
            filename=vchasno_file_name,
            title=cleared_name,
            # Optional params
            amount=int(self.amount*100),
            category=self.category or 0,
            date_document=date,
            doc_number=self.number,
            recipient_edrpou=self.edrpou_recipient,
            recipient_emails=emails,
            expected_owner_signatures=self.owner_signatire_count,
            expected_recipient_signatures=self.recipient_signatire_count,
            first_sign_by=self.first_sign_by,
        )
        if res:
            document = self.env['kw.vchasno.document']
            for vals in res['documents']:
                document_id = document.updates_document(vals)
                document_id.write({
                    'ir_attachment_id': attachment.id,
                    'vchasno_id': self.vchasno_id.id,
                    'edrpou_owner': self.edrpou_owner,
                    'email_owner': self.vchasno_id.email_owner,
                    'company_name_owner': self.vchasno_id.name,
                    'edrpou_recipient': self.edrpou_recipient,
                    'contact_id': self.contact_id.id if
                    self.contact_id else False,
                    'email_recipient': self.email_recipient,
                    'first_sign_by': self.first_sign_by,
                })
                self.write_vchasno_params(document_id)
                if self.send_immediately:
                    vchasno_api.send_document_to_recipient(
                        vchasno_doc_id=document_id,
                        vchasno_ref=vals['id'],
                    )
        else:
            raise exceptions.ValidationError(
                _('The document is not loaded into the system'))
        return {
            'type': 'ir.actions.client',
            'tag': 'reload', }
