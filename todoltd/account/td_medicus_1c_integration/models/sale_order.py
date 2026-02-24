import collections
import itertools

from datetime import date
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
from itertools import groupby


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    budget_funds = fields.Boolean(
        related='td_agreement_id.budget_funds',
        string="Agreement Budget Funds"
    )
    td_budget_funds = fields.Boolean(
        related='td_agreement_id.budget_funds',
        string="Tax Invoice Budget Funds"
    )
    td_show_create_invoice = fields.Boolean(
        compute='_compute_td_show_create_invoice',
        string="Show Create Invoice Button"
    )
    td_tax_guide_id = fields.Many2one(
        comodel_name='account.tax',
        compute='_compute_td_tax_guide_id',
        readonly=False,
        string="Order Tax Guide"
    )
    td_tax_invoice_count = fields.Integer(
        compute='_compute_td_tax_invoices',
        string="Tax Invoices Count"
    )
    td_tax_invoice_ids = fields.One2many(
        comodel_name='td.tax.invoice',
        inverse_name='sale_order_id',
        string="Tax Invoices List"
    )
    td_tax_invoice_state = fields.Selection(
        [
            ('budget', 'Budget funds'),
            ('not_created', 'Not created'),
            ('draft', 'Draft'),
            ('confirm', 'Confirm'),
            ('confirm_finish', 'Confirmed (no adjustments are possible)'),
            ('cancel', 'Cancel'),
        ],
        compute='_compute_td_tax_invoice_state',
        default='draft',
        store=True,
        string="Tax Invoice Status"
    )
    td_tax_invoice_state_percentage = fields.Float(
        compute='_compute_td_tax_invoice_state',
        store=True,
        string="Tax Invoice Completion %"
    )

    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_amounts(self):
        account_tax = self.env['account.tax']
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type and not x.is_downpayment)
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()
            account_tax._add_tax_details_in_base_lines(base_lines, order.company_id)
            account_tax._round_base_lines_tax_details(base_lines, order.company_id)
            tax_totals = account_tax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )
            order.amount_untaxed = tax_totals['base_amount_currency']
            order.amount_tax = tax_totals['tax_amount_currency']
            order.amount_total = tax_totals['total_amount_currency']

    @api.depends('invoice_ids')
    def _compute_td_show_create_invoice(self):
        for order in self:
            delivered = order.invoice_ids.filtered(
                lambda inv: inv.td_advance_payment_method == 'delivered'
            )
            order.td_show_create_invoice = bool(delivered)

    @api.depends('order_line')
    def _compute_td_tax_guide_id(self):
        for order in self:
            if order.order_line:
                # Беремо податок з першого ж рядка
                order.td_tax_guide_id = order.order_line[0].tax_id.id
            else:
                order.td_tax_guide_id = False

    @api.depends('td_tax_invoice_ids', 'td_budget_funds', 'td_tax_invoice_ids.state')
    def _compute_td_tax_invoice_state(self):
        for rec in self:
            rec.td_tax_invoice_state = 'not_created'
            rec.td_tax_invoice_state_percentage = 100.0
            
            states = [line.state for line in rec.td_tax_invoice_ids if line.state]
            if not states:
                continue

            state_counts = collections.Counter(states)
            total = len(states)
            
            state_percentages = {
                state: round((count / total) * 100, 2) 
                for state, count in state_counts.items()
            }
            
            if state_percentages:
                most_common_state = max(state_percentages.items(), key=lambda x: x[1])
                rec.td_tax_invoice_state = most_common_state[0]
                rec.td_tax_invoice_state_percentage = most_common_state[1]

    @api.depends('td_tax_invoice_ids')
    def _compute_td_tax_invoices(self):
        for order in self:
            order.td_tax_invoice_count = len(order.td_tax_invoice_ids)

    @api.depends_context('lang')
    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_tax_totals(self):
        account_tax = self.env['account.tax']
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type and not x.is_downpayment)
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()
            account_tax._add_tax_details_in_base_lines(base_lines, order.company_id)
            account_tax._round_base_lines_tax_details(base_lines, order.company_id)
            order.tax_totals = account_tax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=order.currency_id or order.company_id.currency_id,
                company=order.company_id,
            )

    def _create_invoices(self, grouped=False, final=False, date=None):
        if not self.env['account.move'].has_access('create'):
            try:
                self.check_access('write')
            except AccessError:
                return self.env['account.move']

        invoice_vals_list = []
        invoice_item_sequence = 0
        for order in self:
            if order.partner_invoice_id.lang:
                order = order.with_context(lang=order.partner_invoice_id.lang)
            order = order.with_company(order.company_id)

            invoice_vals = order._prepare_invoice()
            invoiceable_lines = order._get_invoiceable_lines(final)

            if not any(not line.display_type for line in invoiceable_lines):
                continue

            invoice_line_vals = []
            down_payment_section_added = False
            for line in invoiceable_lines:
                if not down_payment_section_added and line.is_downpayment:
                    invoice_line_vals.append(
                        Command.create(
                            order._prepare_down_payment_section_line(sequence=invoice_item_sequence)
                        ),
                    )
                    down_payment_section_added = True
                    invoice_item_sequence += 1
                invoice_line_vals.append(
                    Command.create(
                        dict(
                            line._prepare_invoice_line(sequence=invoice_item_sequence),
                            td_order_line_id=line.id
                        )
                    ),
                )
                invoice_item_sequence += 1

            invoice_vals['invoice_line_ids'] += invoice_line_vals
            invoice_vals_list.append(invoice_vals)

        if not invoice_vals_list and self._context.get('raise_if_nothing_to_invoice', True):
            raise UserError(self._nothing_to_invoice_error_message())

        if not grouped:
            new_invoice_vals_list = []
            invoice_grouping_keys = self._get_invoice_grouping_keys()
            invoice_vals_list = sorted(
                invoice_vals_list,
                key=lambda x: [x.get(grouping_key) for grouping_key in invoice_grouping_keys]
            )
            for _keys, invoices in groupby(invoice_vals_list, key=lambda x: [x.get(k) for k in invoice_grouping_keys]):
                origins, payment_refs, refs = set(), set(), set()
                ref_invoice_vals = None
                for invoice_vals in invoices:
                    if not ref_invoice_vals:
                        ref_invoice_vals = invoice_vals
                    else:
                        ref_invoice_vals['invoice_line_ids'] += invoice_vals['invoice_line_ids']
                    origins.add(invoice_vals['invoice_origin'])
                    payment_refs.add(invoice_vals['payment_reference'])
                    refs.add(invoice_vals['ref'])
                ref_invoice_vals.update({
                    'ref': ', '.join(refs)[:2000],
                    'invoice_origin': ', '.join(origins),
                    'payment_reference': len(payment_refs) == 1 and payment_refs.pop() or False,
                })
                new_invoice_vals_list.append(ref_invoice_vals)
            invoice_vals_list = new_invoice_vals_list

        if len(invoice_vals_list) < len(self):
            sale_order_line = self.env['sale.order.line']
            for invoice in invoice_vals_list:
                sequence = 1
                for line in invoice['invoice_line_ids']:
                    line[2]['sequence'] = sale_order_line._get_invoice_line_sequence(new=sequence, old=line[2]['sequence'])
                    sequence += 1

        moves = self._create_account_invoices(invoice_vals_list, final)

        if final and (moves_to_switch := moves.sudo().filtered(lambda m: m.amount_total < 0)):
            with self.env.protecting([moves._fields['team_id']], moves_to_switch):
                moves_to_switch.action_switch_move_type()
                self.invoice_ids._set_reversed_entry(moves_to_switch)

        for move in moves:
            if final:
                delta_amount = 0
                for order_line in self.order_line:
                    if not order_line.is_downpayment:
                        continue
                    inv_amt = order_amt = 0
                    for invoice_line in order_line.invoice_lines:
                        sign = 1 if invoice_line.move_id.is_inbound() else -1
                        if invoice_line.move_id == move:
                            inv_amt += invoice_line.price_total * sign
                        elif invoice_line.move_id.state != 'cancel':
                            order_amt += invoice_line.price_total * sign
                    if inv_amt and order_amt:
                        delta_amount += inv_amt + order_amt

                if not move.currency_id.is_zero(delta_amount):
                    receivable_line = move.line_ids.filtered(lambda aml: aml.account_id.account_type == 'asset_receivable')[:1]
                    product_lines = move.line_ids.filtered(lambda aml: aml.display_type == 'product' and aml.is_downpayment)
                    tax_lines = move.line_ids.filtered(lambda aml: aml.tax_line_id.amount_type not in (False, 'fixed'))
                    if tax_lines and product_lines and receivable_line:
                        line_commands = [Command.update(receivable_line.id, {'amount_currency': receivable_line.amount_currency + delta_amount})]
                        delta_sign = 1 if delta_amount > 0 else -1
                        for lines, attr, sign in ((product_lines, 'price_total', -1 if move.is_inbound() else 1), (tax_lines, 'amount_currency', 1)):
                            remaining, lines_len = delta_amount, len(lines)
                            for line in lines:
                                if move.currency_id.compare_amounts(remaining, 0) != delta_sign:
                                    break
                                amt = delta_sign * max(move.currency_id.rounding, abs(move.currency_id.round(remaining / lines_len)))
                                remaining -= amt
                                line_commands.append(Command.update(line.id, {attr: line[attr] + amt * sign}))
                        move.line_ids = line_commands

            move.message_post_with_source(
                'mail.message_origin_link',
                render_values={'self': move, 'origin': move.line_ids.sale_line_ids.order_id},
                subtype_xmlid='mail.mt_note',
            )
        return moves

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