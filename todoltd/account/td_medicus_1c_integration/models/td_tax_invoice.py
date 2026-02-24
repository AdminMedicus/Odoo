import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_round

class TdTaxInvoice(models.Model):
    _name = 'td.tax.invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'TD Tax Invoice'

    accounting_date = fields.Date(
        default=fields.Date.context_today
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        default=lambda self: self.env.company
    )
    domain_payment_ids = fields.Many2many(
        comodel_name='account.move.line',
        compute='_compute_domain_payment_ids'
    )
    invoice_id = fields.Many2one(
        comodel_name='account.move'
    )
    invoice_type = fields.Selection(
        [
            ('regular', 'Regular invoicing'),
            ('invoice', 'Invoice'),
        ],
        readonly=True
    )
    move_type = fields.Selection(
        [
            ('tax_inv', 'Tax Invoice'),
            ('adj_inv', 'Adjustment Invoice'),
        ],
        default='tax_inv'
    )
    name = fields.Char(
        default='Draft',
        readonly=True
    )
    narration = fields.Text()
    parent_id = fields.Many2one(
        comodel_name='td.tax.invoice',
        string="Parent Tax Invoice"
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Partner Tax Invoice"
    )
    payment_id = fields.Many2one(
        comodel_name='account.move.line'
    )
    price_total = fields.Float(
        compute='_compute_total_price'
    )
    price_vat = fields.Float(
        compute='_compute_total_price'
    )
    price_with_out_tax = fields.Float(
        compute='_compute_total_price'
    )
    responsible_user_id = fields.Many2one(
        comodel_name='res.users',
        string="Tax Representative"
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order'
    )
    state = fields.Selection(
        [
            ('budget', 'Budget funds'),
            ('not_created', 'Not created'),
            ('draft', 'Draft'),
            ('confirm', 'Confirm'),
            ('confirm_finish', 'Confirmed (no adjustments are possible)'),
            ('cancel', 'Cancel'),
        ],
        default='draft',
        tracking=True
    )
    tax_guide_id = fields.Many2one(
        comodel_name='account.tax',
        compute='_compute_tax_guide_id',
        readonly=False,
        store=True
    )
    td_budget_funds = fields.Boolean(
        related='invoice_id.td_budget_funds'
    )
    td_invoice_line_ids = fields.One2many(
        comodel_name='td.tax.invoice.line',
        inverse_name='td_invoice_id'
    )

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

    @api.depends('td_invoice_line_ids.quantity', 'td_invoice_line_ids.price_with_out_vat')
    def _compute_total_price(self):
        for inv in self:
            rounding = inv.company_id.currency_id.rounding
            total_no_tax = 0.0
            total_vat = 0.0
            total_all = 0.0

            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
                total_no_tax += float_round(
                    line.price_with_out_vat * line.quantity,
                    precision_rounding=rounding
                )
                total_vat += float_round(
                    line.vat_price * line.quantity,
                    precision_rounding=rounding
                )
                total_all += float_round(
                    line.sum_price_with_vat * line.quantity,
                    precision_rounding=rounding
                )

            inv.price_with_out_tax = total_no_tax
            inv.price_vat = total_vat
            inv.price_total = total_all

    @api.onchange('tax_guide_id')
    def _onchange_tax_guide_id(self):
        for inv in self:
            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
            inv._compute_total_price()

    @api.model
    def _update_expired_status(self):
        """Метод-заглушка для запланованої дії (cron)"""
        return True

    def action_cancel_tax_invoice(self):
        for inv in self:
            inv.state = 'cancel'

    def action_confirm_tax_invoice(self):
        for inv in self:
            inv.state = 'confirm'
            year = datetime.datetime.now().year
            padded_id = str(inv.id).zfill(5)
            if inv.parent_id:
                inv.name = f'ADJ/{year}/{padded_id}'
            else:
                inv.name = f'TAX/{year}/{padded_id}'

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

    def action_draft_tax_invoice(self):
        for inv in self:
            inv.state = 'draft'

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

    def recalculation_of_the_quantity_of_lines(self, recalc=True):
        for rec in self:
            if not rec.payment_id or not rec.td_invoice_line_ids:
                continue

            payment_amount = rec.payment_id.credit or 0
            if not payment_amount:
                continue

            total_lines_sum = sum(
                line.sum_price_with_out_vat or 0
                for line in rec.td_invoice_line_ids
            )
            if not total_lines_sum:
                continue

            rounding = rec.company_id.currency_id.rounding
            remaining_amount = payment_amount
            lines = rec.td_invoice_line_ids
            num_lines = len(lines)

            for i, line in enumerate(lines):
                if i == num_lines - 1:
                    line_target_amount = remaining_amount
                else:
                    line_total_orig = line.sum_price_with_out_vat or 0
                    proportion = line_total_orig / total_lines_sum
                    line_target_amount = float_round(
                        payment_amount * proportion,
                        precision_rounding=rounding
                    )
                    remaining_amount -= line_target_amount

                unit_price = line.price_with_out_vat or 1.0
                new_qty = float_round(
                    line_target_amount / unit_price,
                    precision_digits=5
                )

                if rec.state not in ['confirm', 'confirm_finish']:
                    line.quantity = new_qty

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
            rounding = inv.company_id.currency_id.rounding
            total_no_tax = 0.0
            total_vat = 0.0
            total_all = 0.0

            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
                total_no_tax += float_round(
                    line.price_with_out_vat * line.quantity,
                    precision_rounding=rounding
                )
                total_vat += float_round(
                    line.vat_price * line.quantity,
                    precision_rounding=rounding
                )
                total_all += float_round(
                    line.sum_price_with_vat * line.quantity,
                    precision_rounding=rounding
                )

            inv.price_with_out_tax = total_no_tax
            inv.price_vat = total_vat
            inv.price_total = total_all

    @api.model
    def _update_expired_status(self):
        """Метод-заглушка для запланованої дії (cron)"""
        return True

    @api.onchange('tax_guide_id')
    def _onchange_tax_guide_id(self):
        for inv in self:
            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
            inv._compute_total_price()

    def action_cancel_tax_invoice(self):
        for inv in self:
            inv.state = 'cancel'

    def action_confirm_tax_invoice(self):
        for inv in self:
            inv.state = 'confirm'
            year = datetime.now().year
            padded_id = str(inv.id).zfill(5)
            if inv.parent_id:
                inv.name = f'ADJ/{year}/{padded_id}'
            else:
                inv.name = f'TAX/{year}/{padded_id}'

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

    def action_draft_tax_invoice(self):
        for inv in self:
            inv.state = 'draft'

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

    def recalculation_of_the_quantity_of_lines(self, recalc=True):
        for rec in self:
            if not rec.payment_id or not rec.td_invoice_line_ids:
                continue

            payment_amount = rec.payment_id.credit or 0
            if not payment_amount:
                continue

            total_lines_sum = sum(
                line.sum_price_with_out_vat or 0
                for line in rec.td_invoice_line_ids
            )
            if not total_lines_sum:
                continue

            rounding = rec.company_id.currency_id.rounding
            remaining_amount = payment_amount
            lines = rec.td_invoice_line_ids
            num_lines = len(lines)

            for i, line in enumerate(lines):
                if i == num_lines - 1:
                    line_target_amount = remaining_amount
                else:
                    line_total_orig = line.sum_price_with_out_vat or 0
                    proportion = line_total_orig / total_lines_sum
                    line_target_amount = float_round(
                        payment_amount * proportion,
                        precision_rounding=rounding
                    )
                    remaining_amount -= line_target_amount

                unit_price = line.price_with_out_vat or 1.0
                new_qty = float_round(
                    line_target_amount / unit_price,
                    precision_digits=5
                )

                if rec.state not in ['confirm', 'confirm_finish']:
                    line.quantity = new_qty

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
