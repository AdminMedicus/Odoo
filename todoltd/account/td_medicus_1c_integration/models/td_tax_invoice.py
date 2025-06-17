from datetime import datetime
from odoo import models, fields, api, _


class TdTaxInvoice(models.Model):
    _name = 'td.tax.invoice'
    _description = 'TD Tax Invoice'

    name = fields.Char(
        default='Draft',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Partner Tax Invoice"
    )
    parent_id = fields.Many2one(
        comodel_name='td.tax.invoice',
        string="Parent Tax Invoice"
    )
    invoice_id = fields.Many2one(
        comodel_name='account.move'
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order'
    )
    accounting_date = fields.Date(
        default=lambda self: fields.Date.context_today(self)
    )
    tax_guide = fields.Many2one(
        comodel_name='account.tax'
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirm', 'Confirm'),
            ('cancel', 'Cancel'),
        ], default='draft'
    )
    move_type = fields.Selection(
        [
            ('tax_inv', 'Tax Invoice'),
            ('adj_inv', 'Adjustment Invoice'),
        ], default='tax_inv'
    )
    td_invoice_line_ids = fields.One2many(
        comodel_name='td.tax.invoice.line',
        inverse_name='td_invoice_id'
    )
    narration = fields.Text()
    price_with_out_tax = fields.Float()
    price_vat = fields.Float()
    price_total = fields.Float()

    responsible_user_id = fields.Many2one(
        comodel_name='res.users'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company
    )

    @api.onchange('tax_guide')
    def _onchange_tax_guide(self):
        for inv in self:
            for line in inv.td_invoice_line_ids:
                line._onchange_product_id()

    def action_confirm_tax_invoice(self):
        for inv in self:
            inv.state = 'confirm'
            year = datetime.now().year
            padded_id = str(inv.id).zfill(5)
            if inv.parent_id:
                inv.name = f'ADJ/{year}/{padded_id}'
            else:
                inv.name = f'TAX/{year}/{padded_id}'

    def action_draft_tax_invoice(self):
        for inv in self:
            inv.state = 'draft'

    def action_cancel_tax_invoice(self):
        for inv in self:
            inv.state = 'cancel'

    def action_create_adjustment_invoice(self):
        for inv in self:
            new_inv = inv.copy({
                'parent_id': inv.id,
                'state': 'draft',
                'move_type': 'adj_inv',
                'name': _('Draft'),
            })

            for line in inv.td_invoice_line_ids:
                line.copy({
                    'td_invoice_id': new_inv.id
                })

            return {
                'type': 'ir.actions.act_window',
                'name': _('Adjustment Invoice'),
                'res_model': 'td.tax.invoice',
                'view_mode': 'form',
                'res_id': new_inv.id,
                'target': 'current',
            }
        return False

    def action_open_sale_order(self):
        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Sale Order'),
                'res_model': 'sale.order',
                'view_mode': 'form',
                'res_id': self.sale_order_id.id,
                'target': 'current',
            }
        return False

    def action_open_invoice(self):
        if self.invoice_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Invoice'),
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_id.id,
                'target': 'current',
            }
        return False
