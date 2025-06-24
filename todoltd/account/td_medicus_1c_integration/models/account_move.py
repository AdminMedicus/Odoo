from odoo import models, fields, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    td_tax_invoice_id = fields.Many2one(
        comodel_name='td.tax.invoice'
    )
    td_tax_invoice_name = fields.Char(
        compute='_compute_td_tax_invoice_name'
    )
    td_order_id = fields.Many2one(
        comodel_name='sale.order'
    )

    def _compute_td_tax_invoice_name(self):
        for move in self:
            if move.td_tax_invoice_id:
                name = move.td_tax_invoice_id.name
            else:
                name = False
            move.td_tax_invoice_name = name

    def action_create_td_tax_invoice(self):
        for move in self:
            record = self.env['td.tax.invoice'].create({
                'partner_id': move.partner_id.id,
                'invoice_id': move.id,
                'sale_order_id': move.td_order_id.id if move.td_order_id else False,
                'accounting_date': move.invoice_date,
                'move_type': 'tax_inv',
                'td_invoice_line_ids': [
                    (0, 0, {
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'quantity': line.quantity,
                        'product_uom_id': line.product_uom_id.id,
                        'price_with_out_vat': line.price_unit,
                    }) for line in move.invoice_line_ids
                ],
            })
            move.td_tax_invoice_id = record.id
            return {
                'type': 'ir.actions.act_window',
                'name': _('Tax Invoice'),
                'res_model': 'td.tax.invoice',
                'view_mode': 'form',
                'res_id': self.td_tax_invoice_id.id,
                'target': 'current',
            }

    def action_open_td_tax_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tax Invoice'),
            'res_model': 'td.tax.invoice',
            'view_mode': 'form',
            'res_id': self.td_tax_invoice_id.id,
            'target': 'current',
        }
