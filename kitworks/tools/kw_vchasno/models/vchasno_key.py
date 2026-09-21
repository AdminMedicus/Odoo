import logging
import base64
from odoo import models, fields, api, exceptions, _

from .vchasno import VchasnoApi

_logger = logging.getLogger(__name__)


class VchasnoKey(models.Model):
    _name = 'kw.vchasno.key'
    _description = 'Vchasno API Keys'

    name = fields.Char(
        required=True, )
    active = fields.Boolean(
        default=True, )
    token = fields.Char(
        required=True, )
    document_import_initial_date = fields.Date(
        string='Initial date', )
    is_log_enabled = fields.Boolean(
        default=False, )
    edrpou_owner = fields.Char(
        required=True, )
    email_owner = fields.Char(
        required=True, )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company', required=True,
        default=lambda self: self.env.user.company_id, )
    user_id = fields.Many2one(
        comodel_name='res.users',
        default=lambda self: self.env.user.id, required=True, )
    field_contact_info_id = fields.Many2one(
        comodel_name='ir.model.fields',
        default=lambda self:
        self.env['ir.model.fields'].search([
            ('name', '=', 'vat'),
            ('model_id', '=', self.env['ir.model'].search(
                [('model', '=', 'res.partner')], limit=1).id)], limit=1),
        domain=lambda self: [('model_id', '=', self.env['ir.model'].search([
            ('model', '=', 'res.partner')], limit=1).id)],
        help='default field from which EDRPOU and email are taken')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record.update_categories(silent=True)
        return records

    def vchasno_api(self):
        return VchasnoApi(
            api_key=self.token, is_log_enabled=self.is_log_enabled)

    def get_vchasno_document_incoming_list(self):
        vchasno_api = self.vchasno_api()
        params = {
            'date_created_from': self.document_import_initial_date or None,
            'date_created_to': fields.Date.today() or None, }
        documents = vchasno_api.get_incoming_documents(params=params)
        if documents:
            return documents['documents']
        return False

    def get_vchasno_document_outgoing_list(self):
        vchasno_api = self.vchasno_api()
        params = {
            'date_from': self.document_import_initial_date or None,
            'date_to': fields.Date.today() or None, }
        documents = vchasno_api.get_documents(params=params)
        if documents:
            return documents['documents']
        return False

    def get_vchasno_document_file(self, vchasno_ref):
        vchasno_api = self.vchasno_api()
        data = vchasno_api.download_incoming_documents(vchasno_ref)
        return base64.encodebytes(data)

    def get_vchasno_document_archive(self, vchasno_ref):
        vchasno_api = self.vchasno_api()
        data = vchasno_api.download_incoming_archive(vchasno_ref)
        encoded_zip_data = base64.b64encode(data).decode('utf-8')
        return encoded_zip_data

    def update_categories(self, silent=False):
        vchasno_api_id = self.vchasno_api()
        VchasnoCategory = self.env['kw.vchasno.category'].sudo()
        existing_category_refs = \
            VchasnoCategory.search([]).mapped('category_ref')
        try:
            data = vchasno_api_id.get('document-categories/')
        except exceptions.ValidationError as ex_:
            data = []
            if not silent:
                raise ex_
        if data:
            create_list = [
                {
                    'name': category['category_title'],
                    'category_ref': str(category['category_id']),
                }
                for category in data
                if str(category['category_id']) not in existing_category_refs
            ]
            VchasnoCategory.create(create_list)

    def update_incoming_documents(self):
        if self.token and self.active:
            vals_list = self.get_vchasno_document_incoming_list()
            doc = self.env['kw.vchasno.document'].sudo()
            for vals in vals_list:
                document = doc.updates_document(vals)
                if document:
                    data = {'vchasno_id': self.id,
                            'company_name_recipient': self.name,
                            'edrpou_recipient': self.edrpou_owner,
                            'is_incoming': True,
                            'contact_id': self.contact_find(
                                document.edrpou_owner,
                                document.company_name_owner,
                                self),
                            'email_recipient': self.email_owner, }
                    document.write(data)

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

    def update_outgoing_documents(self):
        if self.token and self.active:
            vals_list = self.get_vchasno_document_outgoing_list()
            doc = self.env['kw.vchasno.document'].sudo()
            for vals in vals_list:
                document = doc.updates_document(vals)
                if document:
                    data = {'vchasno_id': self.id,
                            'edrpou_owner': self.edrpou_owner,
                            'email_owner': self.email_owner,
                            'company_name_owner': self.name, }
                    document.write(data)

    def update_document_inf(self):
        if self.token and self.active:
            vchasno_api = self.vchasno_api()
            vals_list = vchasno_api.get_documents(has_changed=1)
            doc = self.env['kw.vchasno.document'].sudo()
            for vals in vals_list['documents']:
                if vals:
                    doc.updates_document(vals)

    def _update_document_inf_cron(self):
        vchasno_key_ids = self.env['kw.vchasno.key'].search(
            [('active', '=', True), ])
        for obj in vchasno_key_ids:
            obj.update_document_inf()

    def _update_documents_cron(self):
        vchasno_key_ids = self.env['kw.vchasno.key'].search(
            [('active', '=', True), ])
        for obj in vchasno_key_ids:
            obj.update_outgoing_documents()
            obj.update_incoming_documents()
            obj.document_import_initial_date = fields.Date.today()

    def document_action(self):
        return {
            'name': _('Vchasno Document'),
            'view_mode': 'list',
            'res_model': 'kw.vchasno.document',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('vchasno_id', '=', self.id)],
            'context': {
                'default_vchasno_id': self.id,
                'search_vchasno_id': self.id}}
