from odoo import fields, models


class SaleMakeInvoiceAdvance(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    def create_invoices(self):
        self._check_amount_is_positive()
        invoices = self._create_invoices(self.sale_order_ids)
        sale_order = self.env.context.get("active_id")
        if sale_order:
            for invoice in invoices:
                invoice.td_order_id = sale_order
        return self.sale_order_ids.action_view_invoice(invoices=invoices)
