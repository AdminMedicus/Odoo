import logging
from datetime import datetime

from odoo import models, fields


_logger = logging.getLogger(__name__)


def datetime_from_format(datetime_str):
    if datetime_str:
        date = datetime.strptime(
            datetime_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')
        return date
    return None


class VchasnoDocument(models.Model):
    _name = 'kw.vchasno.document'
    _description = 'Vchasno Document'

    def _get_selection_status(self):
        selection_state = []
        state_ids = self.env['kw.vchasno.status'].search([])
        for state in state_ids:
            selection_state.append((state.status_ref, state.name))
        return selection_state

    def _get_selection_category(self):
        selection_category = []
        category_ids = self.env['kw.vchasno.category'].search([])
        for category in category_ids:
            selection_category.append((category.category_ref, category.name))
        return selection_category

    name = fields.Char()

    vchasno_ref = fields.Char()

    state = fields.Selection(
        selection='_get_selection_status',
    )
    category = fields.Selection(
        selection='_get_selection_category',
    )
    extension = fields.Char()

    number = fields.Char()

    amount = fields.Float()

    date_created = fields.Datetime()

    date_delivered = fields.Datetime()

    type = fields.Char()

    company_name_owner = fields.Char()

    edrpou_owner = fields.Char()

    email_owner = fields.Char()

    company_name_recipient = fields.Char()

    edrpou_recipient = fields.Char()

    email_recipient = fields.Char()

    url = fields.Char()

    ir_attachment_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='Document Attachment'
    )
    ir_attachment_archive_id = fields.Many2one(
        comodel_name='ir.attachment',
        string='Archive Attachment',
    )
    file = fields.Binary(
        related='ir_attachment_id.datas',
    )
    vchasno_id = fields.Many2one(
        comodel_name='kw.vchasno.key',
    )
    contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contact',
    )
    is_incoming = fields.Boolean(
        default=False,
        readonly=True,
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

    # pylint: disable=R1710
    # pylint: disable=R1705
    def updates_document(self, vals):
        if vals:
            doc = self.env['kw.vchasno.document'].sudo().search([
                ('vchasno_ref', '=', vals['id']), ], limit=1)
            data = self.prepare_document_data(vals)
            if not doc:
                document_id = self.create(data)
                return document_id
            else:
                doc.write(data)
                return False

    def sync_contact(self):
        for obj in self:
            if obj.vchasno_id:
                if not obj.is_incoming and \
                        obj.company_name_recipient and obj.edrpou_recipient:
                    obj.contact_id = obj.contact_find(
                        obj.edrpou_recipient,
                        obj.company_name_recipient, obj.vchasno_id)
                elif obj.is_incoming and \
                        obj.company_name_owner and obj.edrpou_owner:
                    obj.contact_id = obj.contact_find(
                        obj.edrpou_owner,
                        obj.company_name_owner, obj.vchasno_id)

    def contact_find(self, edrpou_owner, company_name_owner, key):
        contact = False
        if key and key.field_contact_info_id:
            field_name = key.field_contact_info_id.name
            if edrpou_owner:
                contact = self.env['res.partner'].search(
                    [(field_name, '=', edrpou_owner)], limit=1).id
                if not contact and company_name_owner:
                    contact = self.env['res.partner'].search(
                        [('name', '=', company_name_owner)], limit=1).id
        return contact

    def prepare_document_data(self, vals):
        data = {
            'vchasno_ref': vals['id'],
            'name': vals['title'],
            'state': str(vals.get('status')),
            'category': str(vals.get('category')),
            'type': vals.get('type'),
            'extension': vals.get('extension'),
            'date_created': datetime_from_format(
                vals.get('date_created')),
            'date_delivered': datetime_from_format(
                vals.get('date_delivered')),
            'edrpou_owner': vals.get('edrpou_owner'),
            'company_name_owner': vals.get('company_name'),
            'url': vals.get('url'),
            'amount': float(vals.get('amount'))/100 if vals.get(
                'amount') else 0,
            'number': vals.get('number'), }
        return data

    # pylint: disable=R1710
    def download_document(self):
        if not self.ir_attachment_id:
            self.download_document_attachment(self.vchasno_ref, 'origin')
        base_url = self.env['ir.config_parameter'].get_param(
            'web.base.url')
        download_url = '/web/content/' \
            + str(self.ir_attachment_id.id) + '?download=true'
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "new",
        }

    # pylint: disable=R1710
    def download_archive_document(self):
        if not self.ir_attachment_archive_id:
            self.download_document_attachment(self.vchasno_ref, 'archive')
        base_url = self.env['ir.config_parameter'].get_param(
            'web.base.url')
        download_url = '/web/content/' \
            + str(self.ir_attachment_archive_id.id) + '?download=true'
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "new",
        }

    def preview_document(self):
        if not self.ir_attachment_id:
            self.download_document_attachment(self.vchasno_ref, 'origin')
        att = self.ir_attachment_id
        token = att.generate_access_token()
        token = token[0] if token else ''
        base_url = self.env['ir.config_parameter'].get_param(
            'web.base.url')
        preview_url = '/web/content/ir.attachment/{}/' \
                      'datas?access_token={}'.format(att.id, token)
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(preview_url),
            "target": "new",
        }

    def download_document_attachment(self, vchasno_ref, types='archive'):
        if types == 'origin':
            data = self.vchasno_id.get_vchasno_document_file(vchasno_ref)
        else:
            data = self.vchasno_id.get_vchasno_document_archive(vchasno_ref)
        if data:
            name = self.name.split('.')[0]
            attachment = self.env['ir.attachment'].create({
                'datas': data,
                'name': '{}{}'.format(
                    name, self.extension if types == 'origin' else '.zip'), })
            if types == 'origin':
                self.ir_attachment_id = attachment.id
            else:
                self.ir_attachment_archive_id = attachment.id

    def send_to_recipient(self):
        self.ensure_one()
        self.vchasno_id.vchasno_api().send_document_to_recipient(
            self, self.vchasno_ref
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
