from datetime import datetime
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
            ('regular', 'Regular invoicing'),
            ('invoice', 'Invoice'),
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
        compute='_compute_total_price',
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

    def action_mass_change_status(self):
        if self.env.user.has_group('td_medicus_1c_integration.group_admin'):
            for rec in self.filtered(
                    lambda rec_: rec_.state != 'confirm_finish'
            ):
                rec.state = 'confirm_finish'
        else:
            raise ValidationError(
                _("You can't change this record "
                  "( you don't have permission)")
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            has_lines = vals.get('td_invoice_line_ids')
            user_is_system = self.env.user._is_system()

            if not has_lines and not user_is_system:
                raise ValidationError(
                    _("You need to add at least one "
                      "line to the document lines")
                )

        return super().create(vals_list)

    def unlink(self):
        if self.env.context.get('skip_state_write_check'):
            return super().unlink()

        if (
                not self.env.context.get('skip_state_write_check')
                and not self.env.user.has_group(
                    'td_medicus_1c_integration.group_admin'
                )
        ):
            for rec in self:
                if rec.state == 'confirm_finish':
                    raise ValidationError(
                        _("You can't change this record "
                          "( you don't have permission)")
                    )

        return super(TdTaxInvoice, self).unlink()

    def write(self, vals):
        if self.env.context.get('skip_state_write_check'):
            return super().write(vals)

        if (
                not self.env.context.get('skip_state_write_check')
                and self.state == 'confirm_finish'
                and not self.env.user.has_group(
                'td_medicus_1c_integration.group_admin')
        ):
            raise ValidationError(
                _("You can't change this record "
                  "( you don't have permission)")
            )

        return super().write(vals)

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
            if not rec.payment_id or not rec.td_invoice_line_ids:
                continue

            payment_amount = rec.payment_id.credit or 0
            if not payment_amount:
                continue

            total = sum(
                line.sum_price_with_out_vat or 0
                for line in rec.td_invoice_line_ids
            )
            if not total:
                continue

            new_quantities = []
            for line in rec.td_invoice_line_ids:
                line_total = line.sum_price_with_out_vat or 0
                proportion = line_total / total if total else 0
                new_line_amount = payment_amount * proportion
                unit_price = line.price_with_out_vat or 1
                new_qty = new_line_amount / unit_price if unit_price else 0

                new_quantities.append((line, round(new_qty, 5)))
            for line, qty in new_quantities:
                if rec.state not in ['confirm', 'confirm_finish']:
                    line.quantity = qty

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

    @api.depends('td_invoice_line_ids')
    def _compute_total_price(self):
        for inv in self:
            price_with_out_tax = []
            price_vat = []
            price_total = []
            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
                price_with_out_tax.append(
                    line.price_with_out_vat * line.quantity
                )
                price_vat.append(line.vat_price * line.quantity)
                price_total.append(
                    line.sum_price_with_vat * line.quantity
                )

            inv.price_with_out_tax = sum(price_with_out_tax)
            inv.price_vat = sum(price_vat)
            inv.price_total = sum(price_total)

    @api.onchange('tax_guide_id')
    def _onchange_tax_guide_id(self):
        for inv in self:
            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
            inv._compute_total_price()

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
