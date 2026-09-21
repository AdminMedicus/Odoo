import logging

from odoo import fields, models, exceptions, _

_logger = logging.getLogger(__name__)


class AccountInvoiceSend(models.TransientModel):
    _inherit = 'account.move.send.wizard'

    def _default_key(self):
        return self.env['kw.vchasno.key'].search(
            [('company_id', '=', self.env.user.company_id.id),
             ('user_id', '=', self.env.user.id), ], limit=1)

    kw_is_vchasno = fields.Boolean(
        default=False, string='Send in Vchasno', )
    vchasno_id = fields.Many2one(
        comodel_name='kw.vchasno.key',
        domain="[('company_id','=',company_id)]",
        default=lambda self: self._default_key(), )

    def send_and_print_action(self):
        res = super().send_and_print_action()
        if self.kw_is_vchasno:
            invoice_id = self.invoice_ids[0]
            for partner_id in self.partner_ids:
                if not partner_id or not partner_id.kw_is_vchasno:
                    raise exceptions.ValidationError(
                        _('Wrong! This partner is'
                          ' not a Vchasno user - {}').format(partner_id.name))
                for attachment in self.attachment_ids:
                    if attachment:
                        context = {
                            'default_amount':
                                float(invoice_id.amount_total_signed),
                            'default_edrpou_owner':
                                self.vchasno_id.edrpou_owner,
                            'default_edrpou_recipient': partner_id.vat,
                            'default_company_id': self.company_id.id,
                            'default_vchasno_id': self.vchasno_id.id,
                            'default_type': self.subject,
                            'default_ir_attachment_id': attachment.id,
                            'default_number': invoice_id.name,
                            'default_email_recipient': partner_id.email,
                            'default_partner_id': partner_id.id,
                            'default_category': '2', }
                        download_vchasno_id = self.env[
                            'vchasno.download.document.wizard'].with_context(
                                **context).create({})
                        download_vchasno_id.add_document()
        return res


class AccountInvoiceBatchWizard(models.TransientModel):
    _inherit = 'account.move.send.batch.wizard'

    def _default_key(self):
        return self.env['kw.vchasno.key'].search(
            [('company_id', '=', self.env.user.company_id.id),
             ('user_id', '=', self.env.user.id), ], limit=1)

    kw_is_vchasno = fields.Boolean(
        default=False, string='Send in Vchasno', )
    company_id = fields.Many2one(
        comodel_name='res.company', string='Company',
        default=lambda self: self.env.user.company_id, )
    vchasno_id = fields.Many2one(
        comodel_name='kw.vchasno.key',
        domain="[('company_id','=',company_id)]",
        default=lambda self: self._default_key(), )

    def send_and_print_action(self):
        res = super().send_and_print_action()
        if self.kw_is_vchasno:
            invoice_id = self.invoice_ids[0]
            for partner_id in self.partner_ids:
                if not partner_id or not partner_id.kw_is_vchasno:
                    raise exceptions.ValidationError(
                        _('Wrong! This partner is'
                          ' not a Vchasno user - {}').format(partner_id.name))
                for attachment in self.attachment_ids:
                    if attachment:
                        context = {
                            'default_amount':
                                float(invoice_id.amount_total_signed),
                            'default_edrpou_owner':
                                self.vchasno_id.edrpou_owner,
                            'default_edrpou_recipient': partner_id.vat,
                            'default_company_id': self.company_id.id,
                            'default_vchasno_id': self.vchasno_id.id,
                            'default_type': self.subject,
                            'default_ir_attachment_id': attachment.id,
                            'default_number': invoice_id.name,
                            'default_email_recipient': partner_id.email,
                            'default_partner_id': partner_id.id,
                            'default_category': '2', }
                        download_vchasno_id = self.env[
                            'vchasno.download.document.wizard'].with_context(
                                **context).create({})
                        download_vchasno_id.add_document()
        return res
