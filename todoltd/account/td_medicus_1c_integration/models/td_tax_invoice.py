from datetime import date, datetime, timedelta
from calendar import monthrange
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TdTaxInvoice(models.Model):
    _name = 'td.tax.invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'TD Tax Invoice'

    name = fields.Char(
        default='Draft',
        readonly=True
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
        default=fields.Date.context_today
    )
    tax_guide_id = fields.Many2one(
        comodel_name='account.tax',
        compute='_compute_tax_guide_id',
        readonly=False,
        store=True
    )
    state = fields.Selection(
        [
            ('budget', 'Budget funds'),
            ('not_created', 'Not created'),
            ('draft', 'Draft'),
            ('confirm', 'Confirm'),
            ('confirm_finish', 'Confirmed (no adjustments are possible)'),
            ('cancel', 'Cancel'),
        ], default='draft',
        tracking=True
    )
    td_budget_funds = fields.Boolean(
        default=False,
        related='invoice_id.td_budget_funds'
    )
    move_type = fields.Selection(
        [
            ('tax_inv', 'Tax Invoice'),
            ('adj_inv', 'Adjustment Invoice'),
        ], default='tax_inv'
    )
    invoice_type = fields.Selection(
        [
            ('regular', 'Regular invoicing'), # Регулярне виставлення рахунку
            ('invoice', 'Invoice'), # Рахунок фактура
        ],
        readonly=True
    )
    payment_id = fields.Many2one(
        comodel_name='account.move.line'
    )
    domain_payment_ids = fields.Many2many(
        comodel_name='account.move.line',
        compute='_compute_domain_payment_ids'
    )
    td_invoice_line_ids = fields.One2many(
        comodel_name='td.tax.invoice.line',
        inverse_name='td_invoice_id'
    )
    narration = fields.Text()
    price_with_out_tax = fields.Float(
        compute='_compute_total_price'
    )
    price_vat = fields.Float(
        compute='_compute_total_price'
    )
    price_total = fields.Float(
        compute='_compute_total_price'
    )

    responsible_user_id = fields.Many2one(
        comodel_name='res.users'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company
    )

    @api.model
    def create(self, values):
        if not values.get('td_invoice_line_ids'):
            raise ValidationError(_("You need to add at least one line to the document lines"))

        self._update_status_on_month_day()

        return super().create(values)

    def unlink(self):
        if self.env.context.get('skip_state_write_check'):
            return super().unlink()

        if (
                not self.env.context.get('skip_state_write_check')
                and self.state == 'confirm_finish'
                and not self.env.user.has_group('td_medicus_1c_integration.group_admin')
        ):
            raise ValidationError(_("You can't change this record ( you don't have permission)"))

        self._update_status_on_month_day()

        return super(TdTaxInvoice, self).unlink()

    def write(self, values):
        if self.env.context.get('skip_state_write_check'):
            return super().write(values)

        if (
                not self.env.context.get('skip_state_write_check')
                and self.state == 'confirm_finish'
                and not self.env.user.has_group('td_medicus_1c_integration.group_admin')
        ):
            raise ValidationError(_("You can't change this record ( you don't have permission)"))

        self._update_status_on_month_day()

        return super().write(values)

    @api.depends('invoice_id')
    def _compute_tax_guide_id(self):
        for rec in self:
            if rec.invoice_id:
                if rec.invoice_id.td_tax_guide_id:
                    rec.tax_guide_id = rec.invoice_id.td_tax_guide_id.id
                else:
                    rec.tax_guide_id = rec.tax_guide_id or False
            else:
                rec.tax_guide_id = rec.tax_guide_id or False

    def recalculation_of_the_quantity_of_lines(self, recalc=True):
        for rec in self:
            record = list(
                filter(
                    lambda rec_: rec_['aml_id'] == rec.payment_id.id,
                    rec.invoice_id._get_all_reconciled_invoice_partials()
                )
            )
            if record:
                amount = record[0]['amount']
                lines_data = []

                total = sum(line.price_with_vat for line in rec.td_invoice_line_ids if line.price_with_vat)

                for line in rec.td_invoice_line_ids:
                    line_total = line.price_with_vat
                    percent = (line_total / total) * 100 if total else 0
                    percent_qty = (line.quantity * percent) / 100

                    lines_data.append({
                        'id': line.id,
                        'quantity': line.quantity,
                        'percent': round(percent, 2),
                        'percent_qty': round(percent_qty, 2),
                    })

                for line_ in lines_data:
                    line = rec.td_invoice_line_ids.filtered(lambda l: l.id == line_['id'])
                    if line and line_.get('percent'):
                        line.quantity = (line_.get('percent_qty') * amount) / (line_.get('percent') * total / 100)

    @api.depends('invoice_id')
    def _compute_domain_payment_ids(self):
        for rec in self:
            if rec.invoice_id:
                rec.domain_payment_ids = [
                    (6, 0, [
                        data['aml_id']
                        for data in rec.invoice_id.sudo(
                        )._get_all_reconciled_invoice_partials()
                    ])
                ]
            else:
                rec.domain_payment_ids = False

    @api.depends('td_invoice_line_ids.quantity')
    def _compute_total_price(self):
        for inv in self:
            price_with_out_tax = []
            price_vat = []
            price_total = []
            for line in inv.td_invoice_line_ids:
                price_with_out_tax.append(line.sum_price_with_out_vat)
                price_vat.append(line.vat_price)
                price_total.append(line.price_with_vat)
            inv.price_with_out_tax = sum(price_with_out_tax)
            inv.price_vat = sum(price_vat)
            inv.price_total = sum(price_total)

    @api.onchange('tax_guide_id')
    def _onchange_tax_guide_id(self):
        for inv in self:
            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
            inv._compute_total_price()

    def _update_expired_status(self):

        tax_records = self.env['td.tax.invoice'].search([
            ('accounting_date', '!=', False),
            ('state', '!=', 'confirm_finish'),
        ])

        for tax_rec in tax_records:
            tax_rec._update_status_on_month_day()

    def _update_status_on_month_day(self):
        days = int(self.env['ir.config_parameter'].sudo().get_param(
            'td_days_for_tax_invoice_confirm', default=0))

        check_day = days
        today = date.today()

        rec = self.sudo()

        record_date = rec.accounting_date
        if isinstance(record_date, datetime):
            record_date = record_date.date()

        if rec.accounting_date:
            if record_date.day < check_day:
                first_target_date = record_date.replace(day=check_day)
            else:
                year = record_date.year + (1 if record_date.month == 12 else 0)
                month = 1 if record_date.month == 12 else record_date.month + 1
                try:
                    first_target_date = date(year, month, check_day)
                except ValueError:
                    last_day = monthrange(year, month)[1]
                    first_target_date = date(year, month, min(check_day, last_day))

            if first_target_date <= today:
                rec.with_context(skip_state_write_check=True).write({
                    'state': 'confirm_finish'
                })

            if rec.sale_order_id:
                rec.sale_order_id._compute_td_tax_invoice_state()

    def action_confirm_tax_invoice(self):
        for inv in self:
            inv.state = 'confirm'
            year = datetime.now().year
            padded_id = str(inv.id).zfill(5)
            if inv.parent_id:
                inv.name = f'ADJ/{year}/{padded_id}'
            else:
                inv.name = f'TAX/{year}/{padded_id}'

            self._update_status_on_month_day()

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
