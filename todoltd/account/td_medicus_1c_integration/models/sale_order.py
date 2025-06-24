from odoo import models, fields, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_tax_invoice_ids = fields.Many2many(
        comodel_name='td.tax.invoice',
        compute='_compute_td_tax_invoices'
    )
    td_tax_invoice_count = fields.Integer(
        compute='_compute_td_tax_invoices'
    )

    def _compute_td_tax_invoices(self):
        for move in self:
            td_tax_inv_ids = self.env['td.tax.invoice'].search([(
                'sale_order_id', '=', move.id
            )])
            move.td_tax_invoice_ids = [(6, 0, [tax.id for tax in td_tax_inv_ids])]
            move.td_tax_invoice_count = len(td_tax_inv_ids)

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
