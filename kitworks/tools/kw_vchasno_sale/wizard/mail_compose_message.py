import logging

from odoo import fields, models, exceptions, _
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _default_key(self):
        return self.env['kw.vchasno.key'].search([
            ('company_id', '=', self.env.user.company_id.id),
            ('user_id', '=', self.env.user.id),
        ], limit=1)

    kw_is_vchasno = fields.Boolean(
        default=False,
        string='Send in Vchasno',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.user.company_id,
    )
    vchasno_id = fields.Many2one(
        comodel_name='kw.vchasno.key',
        domain="[('company_id', '=', company_id)]",
        default=lambda self: self._default_key(),
    )
    kw_first_sign_by = fields.Selection(
        string="First Sign By",
        selection=[
            ("owner", "Owner"),
            ("recipient", "Recipient"),
        ],
        default="recipient",
        ondelete={"recipient": "set default"},
        help='Defines who should sign the document first.\n'
        'Owner: Partner selected in the field "Vchasno"(vchasno_id)\n'
        'Recipient: Partners selected in the field "Recipients"(partner_ids)',
    )

    def _action_send_mail(self, auto_commit=False):
        if self.kw_is_vchasno:
            res_ids = self.res_ids if isinstance(self.res_ids, list) \
                else safe_eval(self.res_ids)

            sale_order_ids = self.env['sale.order'].search([
                ('id', 'in', res_ids),
            ])
            if not sale_order_ids:
                raise exceptions.ValidationError(
                    _("No related Sale Orders found for the given IDs."))

            for sale_order in sale_order_ids:
                for partner_id in self.partner_ids:
                    if not partner_id or not partner_id.kw_is_vchasno:
                        raise exceptions.ValidationError(
                            _('Wrong! This partner is not a Vchasno user - {}')
                            .format(partner_id.name))
                    if not partner_id.vat:
                        raise exceptions.ValidationError(
                            _('Partner "{}" does not have a VAT number set, '
                              'required for EDRPOU Recipient.')
                            .format(partner_id.name))

                    for attachment in self.attachment_ids:
                        if attachment:
                            context = {
                                'default_amount': float(
                                    sale_order.amount_total),
                                'default_edrpou_owner': (
                                    self.vchasno_id.edrpou_owner),
                                'default_edrpou_recipient': partner_id.vat,
                                'default_company_id': self.company_id.id,
                                'default_vchasno_id': self.vchasno_id.id,
                                'default_type': self.subject,
                                'default_ir_attachment_id': attachment.id,
                                'default_number': sale_order.name,
                                'default_email_recipient': partner_id.email,
                                'default_partner_id': partner_id.id,
                                'default_category': '13',
                                'default_first_sign_by': (
                                    self.kw_first_sign_by),
                            }
                            download_vchasno_id = self.env[
                                'vchasno.download.document.wizard'
                            ].with_context(**context).create({})
                            download_vchasno_id.add_document()

        return super(MailComposeMessage, self)._action_send_mail(
            auto_commit=auto_commit)
