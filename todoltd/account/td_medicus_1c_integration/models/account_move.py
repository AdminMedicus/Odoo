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
                        'price_with_out_vat': line.price_unit,
                    }) for line in move.invoice_line_ids
                ],
            }
            if move.td_advance_payment_method:
                if move.td_advance_payment_method == 'delivered':
                    record_data['invoice_type'] = 'regular'
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
            'domain': [('id', 'in', self.td_tax_invoice_id.ids)],
            'target': 'current',
        }
