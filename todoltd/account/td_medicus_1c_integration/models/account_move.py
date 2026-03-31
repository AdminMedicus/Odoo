import re

from collections import Counter
from itertools import groupby

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, float_is_zero
from lxml import etree


class AccountMove(models.Model):
    _inherit = 'account.move'

    td_advance_payment_method = fields.Selection(
        default='delivered',
        selection=[
            ('delivered', "Regular invoice"),
            ('fixed', "Down payment (fixed amount)"),
            ('percentage', "Down payment (percentage)"),
        ],
    )
    td_budget_funds = fields.Boolean(
        related='td_order_id.budget_funds'
    )
    td_order_id = fields.Many2one(
        comodel_name='sale.order'
    )
    td_paid_invoice = fields.Boolean()
    td_picking_id = fields.Many2one(
        comodel_name="stock.picking",
        copy=False,
        index=True,
        string="Receipt",
    )
    td_prepayment = fields.Boolean()
    td_tax_guide_id = fields.Many2one(
        comodel_name='account.tax',
        related='td_order_id.td_tax_guide_id'
    )
    td_tax_invoice_id = fields.Many2one(
        comodel_name='td.tax.invoice'
    )
    td_tax_invoice_ids = fields.Many2many(
        comodel_name='td.tax.invoice',
        store=True
    )
    td_tax_invoice_name = fields.Char(
        compute='_compute_td_tax_invoice_name'
    )
    td_tax_totals = fields.Binary(
        compute='_compute_td_tax_totals'
    )

    def _get_next_sequence_format(self):
        format_string, format_values = super()._get_next_sequence_format()
        if self:
            move = self[0]
            if move.td_prepayment:
                format_values['prefix1'] = "RAH-F/"
            else:
                format_values['prefix1'] = "INV/"
        return format_string, format_values

    @api.depends(
        'date',
        'journal_id',
        'move_type',
        'origin_payment_id',
        'posted_before',
        'state',
    )
    def _compute_name(self):
        self = self.sorted(lambda m: (m.date, m.ref or '', m._origin.id))
        for move in self:
            if move.state == 'cancel':
                continue
            move_has_name = move.name and move.name != '/'
            if not move.posted_before and not move._sequence_matches_date():
                move.name = False
                continue
            if move.date and not move_has_name and move.state != 'draft':
                move._set_next_sequence()
        self._inverse_name()

    def _compute_td_tax_invoice_name(self):
        for move in self:
            move.td_tax_invoice_name = move.td_tax_invoice_id.name if move.td_tax_invoice_id else False

    @staticmethod
    def extract_report_keys(xml_string):
        """Повертає всі ключі report_data та company_info з шаблону QWeb."""
        root = etree.fromstring(xml_string)
        report_keys = set()
        company_keys = set()

        for elem in root.iter():
            for attr in ['t-esc', 't-field']:
                val = elem.attrib.get(attr)
                if not val:
                    continue
                m1 = re.findall(r"report_data\[['\"](\w+)['\"]\]", val)
                report_keys.update(m1)
                m2 = re.findall(r"report_data\[['\"]company_info['\"]\]\[['\"](\w+)['\"]\]", val)
                company_keys.update(m2)
        return list(report_keys), list(company_keys)

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
                    missing_fields[field] = 30 
                elif field == 'co_delivery_period':
                    missing_fields[field] = 7
                elif field == 'co_delivery_terms':
                    missing_fields[field] = 'EXW'
                elif field == 'co_manager':
                    missing_fields[field] = safe_get(self, 'invoice_user_id.name') or 'Менеджер'
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
        report_data['groups'] = self.invoice_line_ids.filtered(lambda l: l.display_type != 'line_section')

        return report_data

    @api.depends(
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.full_reconcile_id',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.payment_id.state',
        'line_ids.td_paid_price',
        'state',
        'td_order_id',
        'td_paid_invoice',
    )
    def _compute_amount(self):
        for move in self:
            total_untaxed, total_untaxed_currency = 0.0, 0.0
            total_tax, total_tax_currency = 0.0, 0.0
            total_residual, total_residual_currency = 0.0, 0.0
            total, total_currency = 0.0, 0.0
            td_paid_price_sum = 0.0

            for line in move.line_ids:
                if hasattr(line, 'td_paid_price') and line.td_paid_price:
                    td_paid_price_sum += float_round(line.td_paid_price, precision_digits=2)

                if move.is_invoice(True):
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type in ('product', 'rounding'):
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type == 'payment_term':
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            sign = move.direction_sign
            move.amount_untaxed = sign * total_untaxed_currency
            move.amount_tax = sign * total_tax_currency
            move.amount_total = sign * total_currency

            move.amount_residual = -sign * float_round(total_residual_currency - td_paid_price_sum, precision_digits=2)
            move.amount_residual_signed = float_round(total_residual - td_paid_price_sum, precision_digits=2)
            move.amount_untaxed_signed = -total_untaxed
            move.amount_untaxed_in_currency_signed = -total_untaxed_currency
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(sign * move.amount_total)
            
            # if move.is_invoice(True) and move.td_order_id:
            #     if not move.td_prepayment:
            #         other_invoices = move.td_order_id.invoice_ids.filtered(lambda inv: inv.id != move.id)
            #         if any(inv.td_prepayment for inv in other_invoices):
            #             move.amount_residual = 0.0
            #             move.amount_residual_signed = 0.0
            #             move.td_paid_invoice = True

    @api.depends_context('lang')
    @api.depends(
        'amount_total',
        'currency_id',
        'invoice_line_ids.currency_rate',
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.price_total',
        'invoice_line_ids.tax_base_amount',
        'invoice_line_ids.tax_line_id',
        'invoice_payment_term_id',
        'partner_id',
        # 'td_paid_invoice',
    )
    def _compute_tax_totals(self):
        for move in self:
            if move.is_invoice(include_receipts=True):
                base_lines, _tax_lines = move._get_rounded_base_and_tax_lines()
                summary = self.env['account.tax']._get_tax_totals_summary(
                    base_lines=base_lines,
                    company=move.company_id,
                    currency=move.currency_id,
                    cash_rounding=move.invoice_cash_rounding_id,
                )
                if summary and 'total_amount_currency' in summary:
                    if summary['total_amount_currency'] != move.amount_total:
                        diff = move.amount_total - summary['total_amount_currency']
                        summary['total_amount_currency'] = move.amount_total
                        if summary.get('groups_by_subtotal'):
                            for subtotal_name in summary['groups_by_subtotal']:
                                groups = summary['groups_by_subtotal'][subtotal_name]
                                if groups:
                                    groups[-1]['tax_group_amount_currency'] += diff
                                    break
                summary['display_in_company_currency'] = (
                        move.company_id.display_invoice_tax_company_currency
                        and move.company_currency_id != move.currency_id
                        and summary['has_tax_groups']
                        and move.is_sale_document(include_receipts=True)
                )
                # if move.td_paid_invoice:
                #     summary = self._zero_tax_amounts(summary)
                move.tax_totals = summary
                move.td_tax_totals = summary
            else:
                move.tax_totals = None
                move.td_tax_totals = None

    @api.depends_context('lang')
    @api.depends(
        'currency_id',
        'invoice_line_ids.currency_rate',
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.price_total',
        'invoice_line_ids.tax_base_amount',
        'invoice_line_ids.tax_line_id',
        'invoice_payment_term_id',
        'partner_id',
        # 'td_paid_invoice',
    )
    def _compute_td_tax_totals(self):
        self._compute_tax_totals()

    # def _zero_tax_amounts(self, tax_totals: dict) -> dict:
    #     if not tax_totals:
    #         return tax_totals
    #     tax_totals = dict(tax_totals)
    #     for key in ['tax_amount', 'tax_amount_currency', 'total_amount', 'total_amount_currency']:
    #         if key in tax_totals:
    #             tax_totals[key] = 0.0
    #     for subtotal in tax_totals.get('subtotals', []):
    #         subtotal['tax_amount_currency'] = 0.0
    #         subtotal['tax_amount'] = 0.0
    #         for group in subtotal.get('tax_groups', []):
    #             group['tax_amount_currency'] = 0.0
    #             group['tax_amount'] = 0.0
    #     return tax_totals

    def action_create_td_tax_invoice(self):
        for move in self:
            record_data = {
                'accounting_date': move.invoice_date,
                'invoice_id': move.id,
                'move_type': 'tax_inv',
                'partner_id': move.partner_id.id,
                'sale_order_id': move.td_order_id.id if move.td_order_id else False,
                'tax_guide_id': move.td_tax_guide_id.id if move.td_tax_guide_id else False,
                'td_invoice_line_ids': [
                    (0, 0, {
                        'invoice_line_id': line.id,
                        'name': line.name,
                        'price_with_out_vat': float_round(
                            line.td_order_line_id.price_unit if line.td_order_line_id else line.price_unit, 
                            precision_digits=2
                        ),
                        'product_id': line.product_id.id,
                        'product_uom_id': line.product_uom_id.id,
                        'quantity': line.quantity,
                        'td_sale_order_line_id': line.td_order_line_id.id if line.td_order_line_id else False,
                    }) for line in move.invoice_line_ids
                ],
            }
            if move.td_advance_payment_method == 'delivered':
                record_data['invoice_type'] = 'regular'
                record_data['td_invoice_line_ids'] = self.recalculation_of_the_quantity_of_lines()
            else:
                record_data['invoice_type'] = 'invoice'

            record = self.env['td.tax.invoice'].create(record_data)
            record._compute_total_price()
            if record_data['invoice_type'] == 'regular':
                move.td_tax_invoice_id = record.id
            else:
                move.td_tax_invoice_ids = [(4, record.id)]
            return {
                'res_id': record.id,
                'res_model': 'td.tax.invoice',
                'target': 'current',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
            }

    def recalculation_of_the_quantity_of_lines(self):
        td_tax_inv_ids = self.env['td.tax.invoice'].search([
            ('invoice_type', '=', 'invoice'),
            ('sale_order_id', '=', self.td_order_id.id)
        ])
        product_dict = {}
        for tax_invoice in td_tax_inv_ids:
            for line in tax_invoice.td_invoice_line_ids:
                product_dict[line.product_id] = product_dict.get(line.product_id, 0.0) + line.quantity
        return [
            (0, 0, {
                'invoice_line_id': line.id,
                'name': line.name,
                'price_with_out_vat': float_round(
                    line.td_order_line_id.price_unit if line.td_order_line_id else line.price_unit,
                    precision_digits=2
                ),
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'quantity': line.quantity - product_dict.get(line.product_id, 0.0),
                'td_sale_order_line_id': line.td_order_line_id.id if line.td_order_line_id else False,
            }) for line in self.invoice_line_ids
        ]

    def action_open_td_tax_invoice(self):
        self.ensure_one()
        if self.td_advance_payment_method == 'delivered':
            return {
                'res_id': self.td_tax_invoice_id.id,
                'res_model': 'td.tax.invoice',
                'target': 'current',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
            }
        return {
            'domain': [('id', 'in', self.td_tax_invoice_ids.ids)],
            'res_model': 'td.tax.invoice',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'views': [(False, 'list'), (False, 'form')],
        }


    def _post(self, soft=True):
        for move in self:
            if move.move_type not in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                continue

            c_untaxed_total = 0.0
            for line in move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                res = line.tax_ids.compute_all(
                    line.price_unit, 
                    currency=move.currency_id, 
                    quantity=1.0, 
                    product=line.product_id, 
                    partner=move.partner_id
                )
                unit_untaxed = float_round(res['total_excluded'], precision_digits=2)
                line_untaxed = float_round(unit_untaxed * line.quantity, precision_digits=2)
                c_untaxed_total += line_untaxed
                
            tax_lines_product = move.invoice_line_ids.filtered(lambda l: l.display_type == 'product').mapped('tax_ids')
            tax_rate = tax_lines_product[0].amount / 100.0 if tax_lines_product else 0.0
            c_tax_total = float_round(c_untaxed_total * tax_rate, precision_digits=2)
            c_total = c_untaxed_total + c_tax_total

            diff_total = c_total - move.amount_total
            diff_tax = c_tax_total - move.amount_tax
            diff_untaxed = c_untaxed_total - move.amount_untaxed
            
            if any(not float_is_zero(d, precision_rounding=move.currency_id.rounding) for d in [diff_total, diff_tax, diff_untaxed]):
                term_line = move.line_ids.filtered(lambda l: l.display_type == 'payment_term')[:1]
                tax_line = move.line_ids.filtered(lambda l: l.display_type == 'tax')[:1]
                prod_line = move.line_ids.filtered(lambda l: l.display_type == 'product')[:1]
                

                move_ctx = move.with_context(check_move_validity=False, skip_account_move_synchronization=True)
                
                def force_balance(line, diff):
                    if not line or float_is_zero(diff, precision_rounding=move.currency_id.rounding):
                        return

                    new_balance = line.balance + diff
                    line.with_context(check_move_validity=False, skip_account_move_synchronization=True).write({
                        'debit': new_balance if new_balance > 0 else 0.0,
                        'credit': -new_balance if new_balance < 0 else 0.0,
                        'amount_currency': line.amount_currency + (diff if line.amount_currency > 0 else -diff),
                        'amount_residual': new_balance,
                        'amount_residual_currency': line.amount_currency + (diff if line.amount_currency > 0 else -diff),
                    })

                force_balance(term_line, diff_total)
                force_balance(tax_line, diff_tax)
                force_balance(prod_line, diff_untaxed)

                move_ctx.write({
                    'amount_untaxed': c_untaxed_total,
                    'amount_tax': c_tax_total,
                    'amount_total': c_total,
                })


        res = super()._post(soft)
        
        for move in self:
            if move.move_type not in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                continue
            
            move._compute_tax_totals() 
            
            for line in move.line_ids.filtered(lambda l: l.display_type == 'payment_term'):
                line.with_context(check_move_validity=False).write({
                    'amount_residual': line.balance,
                    'amount_residual_currency': line.amount_currency,
                })

        self.invalidate_recordset()
        self.env['account.move.line'].invalidate_model(['amount_residual', 'amount_residual_currency'])
        
        return res
