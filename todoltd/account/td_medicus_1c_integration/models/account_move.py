from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    td_tax_invoice_id = fields.Many2one(
        comodel_name='td.tax.invoice'
    )
    td_tax_invoice_ids = fields.Many2many(
        comodel_name='td.tax.invoice'
    )
    td_tax_invoice_name = fields.Char(
        compute='_compute_td_tax_invoice_name'
    )
    td_order_id = fields.Many2one(
        comodel_name='sale.order'
    )
    td_tax_guide_id = fields.Many2one(
        comodel_name='account.tax',
        related='td_order_id.td_tax_guide_id'
    )
    td_prepayment = fields.Boolean()
    td_advance_payment_method = fields.Selection(
        selection=[
            ('delivered', "Regular invoice"),
            ('percentage', "Down payment (percentage)"),
            ('fixed', "Down payment (fixed amount)"),
        ],
        default='delivered',
    )
    td_budget_funds = fields.Boolean(
        default=False,
        related='td_order_id.budget_funds'
    )

    def _get_next_sequence_format(self):
        format_string, format_values = super()._get_next_sequence_format()

        for move in self:
            if move.td_prepayment:
                format_values['prefix1'] = "RAH-F/"
            else:
                format_values['prefix1'] = "INV/"

        return format_string, format_values

    @api.depends('posted_before', 'state', 'journal_id', 'date', 'move_type', 'origin_payment_id')
    def _compute_name(self):
        self = self.sorted(lambda m: (m.date, m.ref or '', m._origin.id))

        for move in self:
            if move.state == 'cancel':
                continue

            move_has_name = move.name and move.name != '/'
            if not move.posted_before and not move._sequence_matches_date():
                # The name does not match the date and the move is not the first in the period:
                # Reset to draft
                move.name = False
                continue
            if move.date and not move_has_name and move.state != 'draft':
                move._set_next_sequence()

        self._inverse_name()

    def _compute_td_tax_invoice_name(self):
        for move in self:
            if move.td_tax_invoice_id:
                name = move.td_tax_invoice_id.name
            else:
                name = False
            move.td_tax_invoice_name = name

    def action_create_td_tax_invoice(self):
        for move in self:
            # sale_line_ids
            # self.env['stock.move'].search([('sale_order_id', '=', 158)])
            record_data = {
                'partner_id': move.partner_id.id,
                'invoice_id': move.id,
                'sale_order_id': move.td_order_id.id if move.td_order_id else False,
                'tax_guide_id': move.td_tax_guide_id.id if move.td_tax_guide_id else False,
                'accounting_date': move.invoice_date,
                'move_type': 'tax_inv',
                'td_invoice_line_ids': [
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
                    record_data['td_invoice_line_ids'] = self.recalculation_of_the_quantity_of_lines()
                else:
                    record_data['invoice_type'] = 'invoice'


            record = self.env['td.tax.invoice'].create(record_data)
            if record_data['invoice_type'] == 'regular':
                move.td_tax_invoice_id = record.id
            else:
                move.td_tax_invoice_ids = [(4, record.id)]
            return {
                'type': 'ir.actions.act_window',
                'name': _('Tax Invoice'),
                'res_model': 'td.tax.invoice',
                'view_mode': 'form',
                'res_id': record.id,
                'target': 'current',
            }

    def recalculation_of_the_quantity_of_lines(self):
        td_tax_inv_ids = self.env['td.tax.invoice'].search([
            ('sale_order_id', '=', self.td_order_id.id),
            ('invoice_type', '=', 'invoice')
        ])
        product_dict = {}
        for tax_invoice in td_tax_inv_ids:
            for line in tax_invoice.td_invoice_line_ids:
                if product_dict.get(line.product_id, False):
                    product_dict[line.product_id] = product_dict[line.product_id] + line.quantity
                else:
                    product_dict[line.product_id] = line.quantity
        if not product_dict:
            return False
        return [
            (0, 0, {
                'product_id': line.product_id.id,
                'name': line.name,
                'quantity': line.quantity - product_dict[line.product_id],
                'invoice_line_id': line.id,
                'product_uom_id': line.product_uom_id.id,
                'td_sale_order_line_id': line.td_order_line_id.id
                if line.td_order_line_id else False,
                'price_with_out_vat': line.td_order_line_id.price_unit
                if line.td_order_line_id else line.price_unit,
            }) for line in self.invoice_line_ids
        ]



    def action_open_td_tax_invoice(self):
        self.ensure_one()
        if self.td_advance_payment_method == 'delivered':
            return {
                'type': 'ir.actions.act_window',
                'name': _('Tax Invoice'),
                'res_model': 'td.tax.invoice',
                'view_mode': 'form',
                'res_id': self.td_tax_invoice_id.id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tax Invoice'),
            'res_model': 'td.tax.invoice',
            'views': [(False, 'list'), (False, 'form')],
            'domain': [('id', 'in', self.td_tax_invoice_ids.ids)],
            'target': 'current',
        }

    @api.depends(
        'line_ids.matched_debit_ids.debit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.matched_credit_ids.credit_move_id.move_id.origin_payment_id.is_matched',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
        'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
        'line_ids.balance',
        'line_ids.currency_id',
        'line_ids.amount_currency',
        'line_ids.amount_residual',
        'line_ids.amount_residual_currency',
        'line_ids.payment_id.state',
        'line_ids.full_reconcile_id',
        'line_ids.td_paid_price',
        'state')
    def _compute_amount(self):
        for move in self:
            total_untaxed, total_untaxed_currency = 0.0, 0.0
            total_tax, total_tax_currency = 0.0, 0.0
            total_residual, total_residual_currency = 0.0, 0.0
            total, total_currency = 0.0, 0.0

            td_paid_price_sum = 0.0

            for line in move.line_ids:
                if hasattr(line, 'td_paid_price') and line.td_paid_price:
                    td_paid_price_sum += line.td_paid_price

                if move.is_invoice(True):
                    # === Invoices ===
                    if line.display_type == 'tax' or (line.display_type == 'rounding' and line.tax_repartition_line_id):
                        # Tax amount.
                        total_tax += line.balance
                        total_tax_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type in ('product', 'rounding'):
                        # Untaxed amount.
                        total_untaxed += line.balance
                        total_untaxed_currency += line.amount_currency
                        total += line.balance
                        total_currency += line.amount_currency
                    elif line.display_type == 'payment_term':
                        # Residual amount.
                        total_residual += line.amount_residual
                        total_residual_currency += line.amount_residual_currency
                else:
                    # === Miscellaneous journal entry ===
                    if line.debit:
                        total += line.balance
                        total_currency += line.amount_currency

            sign = move.direction_sign
            move.amount_untaxed = sign * total_untaxed_currency
            move.amount_tax = sign * total_tax_currency
            move.amount_total = sign * total_currency

            move.amount_residual = -sign * (total_residual_currency - td_paid_price_sum)
            move.amount_residual_signed = total_residual - td_paid_price_sum

            move.amount_untaxed_signed = -total_untaxed
            move.amount_untaxed_in_currency_signed = -total_untaxed_currency
            move.amount_tax_signed = -total_tax
            move.amount_total_signed = abs(total) if move.move_type == 'entry' else -total
            move.amount_total_in_currency_signed = abs(move.amount_total) if move.move_type == 'entry' else -(
                    sign * move.amount_total)
