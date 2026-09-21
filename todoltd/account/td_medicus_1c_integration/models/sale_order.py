from collections import Counter
from datetime import date
from itertools import groupby

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Command
from odoo.tools import float_round


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_budget_funds = fields.Boolean(
        string='Budget Funds',
        related='td_agreement_id.budget_funds'
    )
    td_show_create_invoice = fields.Boolean(
        compute='_compute_td_show_create_invoice'
    )
    td_tax_guide_id = fields.Many2one(
        comodel_name='account.tax',
        compute='_compute_td_tax_guide_id',
        readonly=False
    )
    td_tax_invoice_count = fields.Integer(
        compute='_compute_td_tax_invoices'
    )
    td_tax_invoice_ids = fields.Many2many(
        comodel_name='td.tax.invoice',
        store=True
    )
    td_tax_invoice_state = fields.Selection(
        compute='_compute_td_tax_invoice_state',
        default='draft',
        selection=[
            ('budget', 'Budget funds'),
            ('cancel', 'Cancel'),
            ('confirm', 'Confirm'),
            ('confirm_finish', 'Confirmed (no adjustments are possible)'),
            ('draft', 'Draft'),
            ('not_created', 'Not created'),
        ],
        store=True
    )
    td_tax_invoice_state_percentage = fields.Float(
        compute='_compute_td_tax_invoice_state',
        store=True
    )

    @api.depends('order_line.price_subtotal', 'currency_id', 'company_id', 'payment_term_id')
    def _compute_amounts(self):

        AccountTax = self.env['account.tax']
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type and not x.is_downpayment)
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()
            
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            
            tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                company=order.company_id,
                currency=order.currency_id or order.company_id.currency_id,
            )
            

            order.amount_untaxed = tax_totals['base_amount_currency']
            order.amount_tax = tax_totals['tax_amount_currency']
            order.amount_total = tax_totals['total_amount_currency']

            expected_total = sum(
                float_round(
                    line.price_unit * line.product_uom_qty,
                    precision_rounding=order.currency_id.rounding
                )
                for line in order_lines
            )

            if not order.currency_id.is_zero(order.amount_total - expected_total):
                diff = expected_total - order.amount_total
                order.amount_tax += diff
                order.amount_total = expected_total

    @api.depends_context('lang')
    @api.depends('amount_total', 'order_line.price_subtotal', 'currency_id', 'company_id')
    def _compute_tax_totals(self):
        AccountTax = self.env['account.tax']
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type and not x.is_downpayment)
            base_lines = [line._prepare_base_line_for_taxes_computation() for line in order_lines]
            base_lines += order._add_base_lines_for_early_payment_discount()
            
            AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
            
            order.tax_totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                company=order.company_id,
                currency=order.currency_id or order.company_id.currency_id,
            )
            
            if order.tax_totals and 'total_amount_currency' in order.tax_totals:
                if order.tax_totals['total_amount_currency'] != order.amount_total:
                    diff = order.amount_total - order.tax_totals['total_amount_currency']
                    order.tax_totals['total_amount_currency'] = order.amount_total
                    if order.tax_totals.get('groups_by_subtotal'):
                        for subtotal_name in order.tax_totals['groups_by_subtotal']:
                            groups = order.tax_totals['groups_by_subtotal'][subtotal_name]
                            if groups:
                                groups[-1]['tax_group_amount_currency'] += diff
                                break


    def _create_invoices(self, grouped=False, final=False, date=None):
        """ Create invoice(s) for the given Sales Order(s).

        :param bool grouped: if True, invoices are grouped by SO id.
            If False, invoices are grouped by keys returned by :meth:`_get_invoice_grouping_keys`
        :param bool final: if True, refunds will be generated if necessary
        :param date: unused parameter
        :returns: created invoices
        :rtype: `account.move` recordset
        :raises: UserError if one of the orders has no invoiceable lines.
        """
        if not self.env['account.move'].has_access('create'):
            try:
                self.check_access('write')
            except AccessError:
                return self.env['account.move']

        # 1) Create invoices.
        invoice_vals_list = []
        invoice_item_sequence = 0 # Incremental sequencing to keep the lines order on the invoice.
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
                    # Create a dedicated section for the down payments
                    # (put at the end of the invoiceable_lines)
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

        # 2) Manage 'grouped' parameter: group by (partner_id, currency_id).
        if not grouped:
            new_invoice_vals_list = []
            invoice_grouping_keys = self._get_invoice_grouping_keys()
            invoice_vals_list = sorted(
                invoice_vals_list,
                key=lambda x: [
                    x.get(grouping_key) for grouping_key in invoice_grouping_keys
                ]
            )
            for _grouping_keys, invoices in groupby(invoice_vals_list, key=lambda x: [x.get(grouping_key) for grouping_key in invoice_grouping_keys]):
                origins = set()
                payment_refs = set()
                refs = set()
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

        # 3) Create invoices.

        # As part of the invoice creation, we make sure the sequence of multiple SO do not interfere
        # in a single invoice. Example:
        # SO 1:
        # - Section A (sequence: 10)
        # - Product A (sequence: 11)
        # SO 2:
        # - Section B (sequence: 10)
        # - Product B (sequence: 11)
        #
        # If SO 1 & 2 are grouped in the same invoice, the result will be:
        # - Section A (sequence: 10)
        # - Section B (sequence: 10)
        # - Product A (sequence: 11)
        # - Product B (sequence: 11)
        #
        # Resequencing should be safe, however we resequence only if there are less invoices than
        # orders, meaning a grouping might have been done. This could also mean that only a part
        # of the selected SO are invoiceable, but resequencing in this case shouldn't be an issue.
        if len(invoice_vals_list) < len(self):
            SaleOrderLine = self.env['sale.order.line']
            for invoice in invoice_vals_list:
                sequence = 1
                for line in invoice['invoice_line_ids']:
                    line[2]['sequence'] = SaleOrderLine._get_invoice_line_sequence(new=sequence, old=line[2]['sequence'])
                    sequence += 1

        moves = self._create_account_invoices(invoice_vals_list, final)

        # 4) Some moves might actually be refunds: convert them if the total amount is negative
        # We do this after the moves have been created since we need taxes, etc. to know if the total
        # is actually negative or not
        if final and (moves_to_switch := moves.sudo().filtered(lambda m: m.amount_total < 0)):
            with self.env.protecting([moves._fields['team_id']], moves_to_switch):
                moves_to_switch.action_switch_move_type()
                self.invoice_ids._set_reversed_entry(moves_to_switch)

        for move in moves:
            if final:
                # Downpayment might have been determined by a fixed amount set by the user.
                # This amount is tax included. This can lead to rounding issues.
                # E.g. a user wants a 100€ DP on a product with 21% tax.
                # 100 / 1.21 = 82.64, 82.64 * 1,21 = 99.99
                # This is already corrected by adding/removing the missing cents on the DP invoice,
                # but must also be accounted for on the final invoice.

                delta_amount = 0
                for order_line in self.order_line:
                    if not order_line.is_downpayment:
                        continue
                    inv_amt = order_amt = 0
                    for invoice_line in order_line.invoice_lines:
                        sign = 1 if invoice_line.move_id.is_inbound() else -1
                        if invoice_line.move_id == move:
                            inv_amt += invoice_line.price_total * sign
                        elif invoice_line.move_id.state != 'cancel':  # filter out canceled dp lines
                            order_amt += invoice_line.price_total * sign
                    if inv_amt and order_amt:
                        # if not inv_amt, this order line is not related to current move
                        # if no order_amt, dp order line was not invoiced
                        delta_amount += inv_amt + order_amt

                if not move.currency_id.is_zero(delta_amount):
                    receivable_line = move.line_ids.filtered(
                        lambda aml: aml.account_id.account_type == 'asset_receivable')[:1]
                    product_lines = move.line_ids.filtered(
                        lambda aml: aml.display_type == 'product' and aml.is_downpayment)
                    tax_lines = move.line_ids.filtered(
                        lambda aml: aml.tax_line_id.amount_type not in (False, 'fixed'))
                    if tax_lines and product_lines and receivable_line:
                        line_commands = [Command.update(receivable_line.id, {
                            'amount_currency': receivable_line.amount_currency + delta_amount,
                        })]
                        delta_sign = 1 if delta_amount > 0 else -1
                        for lines, attr, sign in (
                            (product_lines, 'price_total', -1 if move.is_inbound() else 1),
                            (tax_lines, 'amount_currency', 1),
                        ):
                            remaining = delta_amount
                            lines_len = len(lines)
                            for line in lines:
                                if move.currency_id.compare_amounts(remaining, 0) != delta_sign:
                                    break
                                amt = delta_sign * max(
                                    move.currency_id.rounding,
                                    abs(move.currency_id.round(remaining / lines_len)),
                                )
                                remaining -= amt
                                line_commands.append(Command.update(line.id, {attr: line[attr] + amt * sign}))
                        move.line_ids = line_commands

            move.message_post_with_source(
                'mail.message_origin_link',
                render_values={'self': move, 'origin': move.line_ids.sale_line_ids.order_id},
                subtype_xmlid='mail.mt_note',
            )
        return moves

    @api.depends('td_tax_invoice_ids', 'td_budget_funds', 'td_tax_invoice_ids.state')
    def _compute_td_tax_invoice_state(self):
        for rec in self:
            rec.td_tax_invoice_state = 'not_created'
            rec.td_tax_invoice_state_percentage = 100
            states = [line.state for line in rec.td_tax_invoice_ids]
            state_counts = Counter(states)
            total = len(states)
            state_percentages = {
                state: round((count / total) * 100, 2) for state, count in state_counts.items()
            } if total > 0 else {}
            if state_percentages:
                most_common_state = max(state_percentages.items(), key=lambda x: x[1])
                rec.td_tax_invoice_state = most_common_state[0]
                rec.td_tax_invoice_state_percentage = most_common_state[-1]

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
        # for tax_invoice in self.td_tax_invoice_ids:
        #     tax_invoice._update_status_on_month_day()
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tax Invoices'),
            'res_model': 'td.tax.invoice',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.td_tax_invoice_ids.ids)],
            'target': 'current',
        }

    def td_get_co_data(self, template_xml=None):
        """Генерує report_data без KeyError для шаблонів."""
        self.ensure_one()
        company = self.company_id
        bank = company.bank_ids[:1] or None

        def safe_get(obj, attr):
            try:
                return getattr(obj, attr, '') if obj else ''
            except Exception:
                return ''

        company_info = {
            'name': safe_get(company, 'name'),
            'email': safe_get(company, 'email'),
            'phone': safe_get(company, 'phone'),
            'vat': safe_get(company, 'vat'),
            'registry': safe_get(company, 'company_registry'),
            'address': safe_get(getattr(company, 'partner_id', None), 'contact_address'),
            'account_position': safe_get(safe_get(company, 'partner_id').property_account_position_id, 'name'),
            'bank_account': safe_get(bank, 'acc_number'),
            'bank_bic': safe_get(safe_get(bank, 'bank_id'), 'bic'),
            'bank_name': safe_get(safe_get(bank, 'bank_id'), 'name'),
            'sertificate_number': safe_get(company, 'td_sertificate_number'),
        }

        for key in company._fields:
            if key.startswith('td_') and key not in company_info:
                company_info[key] = safe_get(company, key)

        company_info['logo'] = safe_get(company, 'logo')
        company_info['logo_web'] = safe_get(company, 'logo_web')

        report_data = {'company_info': company_info}

        for key in self._fields:
            report_data[key] = safe_get(self, key)

        for key in ['co_date', 'create_date', 'write_date']:
            report_data[key] = safe_get(self, key)

        
        missing_fields = {}
        
        required_fields = [
            'co_number', 
            'co_validity_period', 
            'co_delivery_period', 
            'co_delivery_terms',
            'co_manager', 
            'co_manager_number', 
            'consignee', 
            'consignee_code',
            'partner_name', 
            'vendor_name', 
            'recipient_name', 
            'buyer', 
            'shipper',
            'amount_in_words', 
            'tax_guide_name'
        ]
        
        for field in required_fields:
            if field not in report_data:
                if field == 'co_number':
                    missing_fields[field] = safe_get(self, 'name')
                elif field == 'co_validity_period':
                    if self.validity_date:
                        from datetime import date
                        today = date.today()
                        if self.validity_date > today:
                            missing_fields[field] = (self.validity_date - today).days
                        else:
                            missing_fields[field] = 0
                    else:
                        missing_fields[field] = safe_get(self.company_id, 'quotation_validity_days') or 30
                elif field == 'co_delivery_period':
                    missing_fields[field] = 7
                elif field == 'co_delivery_terms':
                    missing_fields[field] = 'EXW'
                elif field == 'co_manager':
                    missing_fields[field] = safe_get(self, 'user_id.name') or 'Менеджер'
                elif field == 'co_manager_number':
                    missing_fields[field] = ''
                elif field == 'consignee':
                    missing_fields[field] = safe_get(self.partner_id, 'name')
                elif field == 'consignee_code':
                    missing_fields[field] = safe_get(self.partner_id, 'company_registry') or safe_get(self.partner_id, 'vat')
                elif field in ['partner_name', 'vendor_name', 'recipient_name', 'buyer', 'shipper']:
                    missing_fields[field] = safe_get(self.partner_id, 'name')
                elif field == 'amount_in_words':
                    amount_total = safe_get(self, 'amount_total')
                    missing_fields[field] = self._get_amount_in_words(float(amount_total) if amount_total else 0)
                elif field == 'tax_guide_name':
                    missing_fields[field] = safe_get(self.td_tax_guide_id, 'name')
        
        report_data.update(missing_fields)

        report_data['groups'] = self.order_line.filtered(lambda l: not l.display_type)

        return report_data
