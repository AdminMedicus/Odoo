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
        readonly=True,
        selection=[
            ('regular', 'Regular invoicing'),
            ('invoice', 'Invoice'),
        ]
    )
    move_type = fields.Selection(
        default='tax_inv',
        selection=[
            ('tax_inv', 'Tax Invoice'),
            ('adj_inv', 'Adjustment Invoice'),
        ]
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
        aggregator="sum",
        compute='_compute_total_price',
        store=True
    )
    price_vat = fields.Float(
        aggregator="sum",
        compute='_compute_total_price',
        store=True
    )
    price_with_out_tax = fields.Float(
        aggregator="sum",
        compute='_compute_total_price',
        store=True
    )
    responsible_user_id = fields.Many2one(
        comodel_name='res.users',
        string="Tax Representative"
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order'
    )
    state = fields.Selection(
        default='draft',
        selection=[
            ('budget', 'Budget funds'),
            ('not_created', 'Not created'),
            ('draft', 'Draft'),
            ('confirm', 'Confirm'),
            ('confirm_finish', 'Confirmed (no adjustments are possible)'),
            ('cancel', 'Cancel'),
        ],
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
                        for data in rec.invoice_id.sudo()._get_all_reconciled_invoice_partials()
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

    @api.depends('td_invoice_line_ids.price_with_out_vat', 'td_invoice_line_ids.quantity')
    def _compute_total_price(self):
        for inv in self:
            rounding = inv.company_id.currency_id.rounding
            total_all = 0.0
            total_no_tax = 0.0
            total_vat = 0.0

            for line in inv.td_invoice_line_ids:
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

            inv.price_total = total_all
            inv.price_vat = total_vat
            inv.price_with_out_tax = total_no_tax

    @api.onchange('tax_guide_id')
    def _onchange_tax_guide_id(self):
        for inv in self:
            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
            inv._compute_total_price()

    @api.model
    def _update_expired_status(self):
        return True

    def action_cancel_tax_invoice(self):
        self.write({'state': 'cancel'})

    def action_confirm_tax_invoice(self):
        for inv in self:
            inv.state = 'confirm'
            year = datetime.datetime.now().year
            padded_id = str(inv.id).zfill(5)
            inv.name = f'ADJ/{year}/{padded_id}' if inv.parent_id else f'TAX/{year}/{padded_id}'

    def action_create_adjustment_invoice(self):
        for inv in self:
            new_inv = inv.copy({
                'move_type': 'adj_inv',
                'name': _('Draft'),
                'parent_id': inv.id,
                'state': 'draft',
            })
            for line in inv.td_invoice_line_ids:
                line.copy({'td_invoice_id': new_inv.id})

            return {
                'res_id': new_inv.id,
                'res_model': 'td.tax.invoice',
                'target': 'current',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
            }
        return False

    def action_draft_tax_invoice(self):
        self.write({'state': 'draft'})

    def action_mass_change_status(self):
        if self.env.user.has_group('td_medicus_1c_integration.group_admin'):
            self.filtered(lambda r: r.state != 'confirm_finish').write({'state': 'confirm_finish'})
        else:
            raise ValidationError(_("You don't have permission to change this record"))

    def action_open_invoice(self):
        if self.invoice_id:
            return {
                'res_id': self.invoice_id.id,
                'res_model': 'account.move',
                'target': 'current',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
            }
        return False

    def action_open_sale_order(self):
        if self.sale_order_id:
            return {
                'res_id': self.sale_order_id.id,
                'res_model': 'sale.order',
                'target': 'current',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
            }
        return False

    def action_update_data(self):
        self.ensure_one()
        move = self.invoice_id
        if not move:
            raise ValidationError(_("No invoice is linked to this tax invoice."))

        record_data = {
            'accounting_date': move.invoice_date,
            'invoice_id': move.id,
            'move_type': 'tax_inv',
            'partner_id': move.partner_id.id,
            'sale_order_id': move.td_order_id.id if move.td_order_id else False,
            'tax_guide_id': move.td_tax_guide_id.id if move.td_tax_guide_id else False,
            'td_invoice_line_ids': [(5, 0, 0)] + [
                (0, 0, {
                    'invoice_line_id': line.id,
                    'name': line.name,
                    'price_with_out_vat': line.td_order_line_id.price_unit if line.td_order_line_id else line.price_unit,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'quantity': line.quantity,
                    'td_sale_order_line_id': line.td_order_line_id.id if line.td_order_line_id else False,
                }) for line in move.invoice_line_ids
            ],
        }

        if move.td_advance_payment_method:
            record_data['invoice_type'] = 'regular' if move.td_advance_payment_method == 'delivered' else 'invoice'
            if move.td_advance_payment_method == 'delivered':
                record_data['td_invoice_line_ids'] = move.recalculation_of_the_quantity_of_lines()

        self.write(record_data)
        self._compute_total_price()
        self.recalculation_of_the_quantity_of_lines()

        return {
            'res_id': self.id,
            'res_model': 'td.tax.invoice',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('td_invoice_line_ids') and not self.env.user._is_system():
                raise ValidationError(_("You need to add at least one line to the document lines"))
        return super().create(vals_list)

    def recalculation_of_the_quantity_of_lines(self, recalc=True):
        for rec in self:
            if not rec.payment_id or not rec.td_invoice_line_ids:
                continue

            payment_amount = rec.payment_id.credit or 0
            if not payment_amount:
                continue

            total_lines_sum = sum(line.sum_price_with_out_vat or 0 for line in rec.td_invoice_line_ids)
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
                    proportion = (line.sum_price_with_out_vat or 0) / total_lines_sum
                    line_target_amount = float_round(payment_amount * proportion, precision_rounding=rounding)
                    remaining_amount -= line_target_amount

                unit_price = line.price_with_out_vat or 1.0
                new_qty = float_round(line_target_amount / unit_price, precision_digits=5)

                if rec.state not in ['confirm', 'confirm_finish']:
                    line.quantity = new_qty

            rec._compute_total_price()

    def unlink(self):
        if not self.env.context.get('skip_state_write_check'):
            if not self.env.user.has_group('td_medicus_1c_integration.group_admin'):
                for rec in self:
                    if rec.state == 'confirm_finish':
                        raise ValidationError(_("You can't delete this record (no permission)"))
        return super().unlink()

    def write(self, vals):
        if not self.env.context.get('skip_state_write_check'):
            if self.state == 'confirm_finish' and not self.env.user.has_group('td_medicus_1c_integration.group_admin'):
                raise ValidationError(_("You can't change this record (no permission)"))
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
            price_with_out_tax = 0.0
            price_vat = 0.0

            for line in inv.td_invoice_line_ids:
                line._compute_product_id()
                price_with_out_tax += line.price_with_out_vat * line.quantity
                price_vat += line.vat_price * line.quantity

            inv.price_with_out_tax = price_with_out_tax
            inv.price_vat = price_vat
            inv.price_total = price_with_out_tax + price_vat

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

    def action_update_data(self):
        self.ensure_one()

        move = self.invoice_id
        if not move:
            raise ValidationError(
                _("No invoice is linked to this tax invoice.")
            )

        record_data = {
            'partner_id': move.partner_id.id,
            'invoice_id': move.id,
            'sale_order_id': move.td_order_id.id
            if move.td_order_id else False,
            'tax_guide_id': move.td_tax_guide_id.id
            if move.td_tax_guide_id else False,
            'accounting_date': move.invoice_date,
            'move_type': 'tax_inv',
            'td_invoice_line_ids': [(5, 0, 0)] + [
                (0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': line.quantity,
                    'invoice_line_id': line.id,
                    'product_uom_id': line.product_uom_id.id,
                    'td_sale_order_line_id': line.td_order_line_id.id
                    if line.td_order_line_id else False,
                    'price_with_out_vat': line.td_order_line_id.price_unit
                    if line.td_order_line_id else line.price_unit,
                }) for line in move.invoice_line_ids
            ],
        }

        if move.td_advance_payment_method:
            if move.td_advance_payment_method == 'delivered':
                record_data['invoice_type'] = 'regular'
                record_data['td_invoice_line_ids'] = (
                    move.recalculation_of_the_quantity_of_lines()
                )
            else:
                record_data['invoice_type'] = 'invoice'

        self.write(record_data)

        self._compute_total_price()

        self.recalculation_of_the_quantity_of_lines()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Tax Invoice'),
            'res_model': 'td.tax.invoice',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }
