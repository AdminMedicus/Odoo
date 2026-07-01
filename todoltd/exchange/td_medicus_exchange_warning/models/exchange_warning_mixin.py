from html import escape

from odoo import fields, models, _
from odoo.addons.mail.models.mail_thread import MailThread


class TdExchangeWarningMixin(models.AbstractModel):
    _name = 'td.exchange.warning.mixin'
    _description = 'Exchange warning helper'

    ata_exchange_has_error = fields.Boolean(
        string='Exchange error',
        copy=False,
        readonly=True,
        index=True)
    ata_exchange_error_message = fields.Text(
        string='Exchange error message',
        copy=False,
        readonly=True)
    ata_exchange_error_method_id = fields.Many2one(
        comodel_name='ata.exchange.method',
        string='Exchange error method',
        copy=False,
        readonly=True,
        ondelete='set null')
    ata_exchange_warning_icon = fields.Html(
        string='Exchange warning',
        compute='_compute_ata_exchange_warning_icon',
        sanitize=False,
        readonly=True)

    def _compute_ata_exchange_warning_icon(self):
        for record in self:
            if record.ata_exchange_has_error:
                title = escape(record.ata_exchange_error_message or _('Exchange failed'), quote=True)
                record.ata_exchange_warning_icon = (
                    '<span class="text-warning" title="%s">'
                    '<i class="fa fa-exclamation-triangle"/></span>'
                ) % title
            else:
                record.ata_exchange_warning_icon = False

    def _ata_exchange_check_add_to_queue(self, vals):
        if self.env.context.get('ata_exchange_warning_skip_queue'):
            return False
        if set(vals).issubset({
            'ata_exchange_has_error',
            'ata_exchange_error_message',
            'ata_exchange_error_method_id',
        }):
            return False
        return super()._ata_exchange_check_add_to_queue(vals)

    def ata_exchange_set_error(self, message, method=None):
        message = message or _('Unknown error')
        for record in self:
            already_same_error = (
                record.ata_exchange_has_error
                and record.ata_exchange_error_message == message
                and record.ata_exchange_error_method_id == method
            )
            with self.env['ata.exchange.queue'].disable_add_temporarily():
                record.sudo().with_context(ata_exchange_warning_skip_queue=True).write({
                    'ata_exchange_has_error': True,
                    'ata_exchange_error_message': message,
                    'ata_exchange_error_method_id': method.id if method else False,
                })
            if not already_same_error and isinstance(record, MailThread):
                record.message_post(
                    body=_('Exchange failed: %s') % message,
                    subtype_xmlid='mail.mt_note')

    def ata_exchange_clear_error(self, method=None):
        for record in self:
            if method and record.ata_exchange_error_method_id and record.ata_exchange_error_method_id != method:
                continue
            if not record.ata_exchange_has_error:
                continue
            with self.env['ata.exchange.queue'].disable_add_temporarily():
                record.sudo().with_context(ata_exchange_warning_skip_queue=True).write({
                    'ata_exchange_has_error': False,
                    'ata_exchange_error_message': False,
                    'ata_exchange_error_method_id': False,
                })

    def action_ata_exchange_retry_exchange(self):
        self.env['ata.exchange.queue'].retry_exchange(self)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Exchange'),
                'message': _('Added to the exchange queue'),
                'type': 'success',
                'sticky': False,
            },
        }


class ProductProductExchangeWarning(models.Model):
    _name = 'product.product'
    _inherit = ['product.product', 'td.exchange.warning.mixin']


class ProductTemplateExchangeWarning(models.Model):
    _name = 'product.template'
    _inherit = ['product.template', 'td.exchange.warning.mixin']


class ResPartnerExchangeWarning(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner', 'td.exchange.warning.mixin']


class TdAgreementExchangeWarning(models.Model):
    _name = 'td.agreement'
    _inherit = ['td.agreement', 'td.exchange.warning.mixin']


class StockPickingExchangeWarning(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'td.exchange.warning.mixin']


class AccountMoveExchangeWarning(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'td.exchange.warning.mixin']


class TdTaxInvoiceExchangeWarning(models.Model):
    _name = 'td.tax.invoice'
    _inherit = ['td.tax.invoice', 'td.exchange.warning.mixin']
