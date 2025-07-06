from datetime import date, timedelta
from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_tax_invoice_ids = fields.Many2many(
        comodel_name='td.tax.invoice',
        compute='_compute_td_tax_invoices'
    )
    td_tax_invoice_count = fields.Integer(
        compute='_compute_td_tax_invoices'
    )
    td_show_create_invoice = fields.Boolean(
        compute='_compute_td_show_create_invoice'
    )
    td_tax_guide_id = fields.Many2one(
        comodel_name='account.tax',
        compute='_compute_td_tax_guide_id',
        readonly=False
    )
    budget_funds = fields.Boolean(
        default=False,
        related='td_agreement_id.budget_funds'
    )
    td_budget_funds = fields.Boolean(
        default=False,
        related='td_agreement_id.budget_funds'
    )
    td_tax_invoice_state = fields.Selection(
        [
            ('budget', 'Budget funds'),
            ('not_created', 'Not created'),
            ('draft', 'Draft'),
            ('confirm', 'Confirm'),
            ('confirm_finish', 'Confirmed (no adjustments are possible)'),
            ('cancel', 'Cancel'),
        ], default='draft',
        compute='_compute_td_tax_invoice_state'
    )

    @api.depends('td_tax_invoice_ids', 'td_budget_funds')
    def _compute_td_tax_invoice_state(self):
        for rec in self:
            days = self.env['ir.config_parameter'].sudo().get_param(
                'td_medicus_1c_integration.td_days_for_tax_invoice_confirm')
            today = date.today()
            end_date = today + timedelta(days=days)

            filtered_records = rec.td_tax_invoice_ids.filtered(
                lambda l: l.accounting_date and today <= l.accounting_date <= end_date
            )

            for filt_rec in filtered_records:
                filt_rec.state = 'confirm_finish'

            if len(rec.td_tax_invoice_ids.filtered(lambda l: l.state == 'confirm_finish')) > 0:
                rec.td_tax_invoice_state = 'confirm_finish'
            elif len(rec.td_tax_invoice_ids) == 0:
                rec.td_tax_invoice_state = 'not_created'
            elif len(rec.td_tax_invoice_ids.filtered(lambda l: l.state == 'draft')) > 0:
                rec.td_tax_invoice_state = 'draft'
            elif rec.td_budget_funds:
                rec.td_tax_invoice_state = 'budget'
            elif len(rec.td_tax_invoice_ids.filtered(lambda l: l.state == 'cancel')) > 0:
                rec.td_tax_invoice_state = 'cancel'
            else:
                rec.td_tax_invoice_state = 'draft'

    def action_confirm(self):
        self.ensure_one()

        low_margin_lines = self.order_line.filtered(
            lambda l: not l.is_downpayment and l.price_unit < l.purchase_price
        )

        if low_margin_lines and not self.env.context.get('force_confirm_low_margin'):
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'td.sale.order.low.margin.warning',
                'view_mode': 'form',
                'target': 'new',
                'context': {'active_id': self.id},
            }

        return super(SaleOrder, self).action_confirm()

    @api.depends('order_line')
    def _compute_td_tax_guide_id(self):
        for order in self:
            if len(order.order_line) > 0:
                for line in order.order_line:
                    order.td_tax_guide_id = line.tax_id.id
                    break
            else:
                order.td_tax_guide_id = False

    @api.depends('invoice_ids')
    def _compute_td_show_create_invoice(self):
        for order in self:
            delivered = order.invoice_ids.filtered(
                lambda inv: inv.td_advance_payment_method == 'delivered'
            )
            if delivered:
                order.td_show_create_invoice = True
            else:
                order.td_show_create_invoice = False

    def _compute_td_tax_invoices(self):
        for move in self:
            td_tax_inv_ids = self.env['td.tax.invoice'].search([(
                'sale_order_id', '=', move.id
            )])
            move.td_tax_invoice_ids = [(6, 0, [tax.id for tax in td_tax_inv_ids])]
            move.td_tax_invoice_count = len(td_tax_inv_ids)

    def action_open_tax_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tax Invoices'),
            'res_model': 'td.tax.invoice',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.td_tax_invoice_ids.ids)],
            'target': 'current',
        }
