from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_invoice_from_delivery = fields.Boolean(
        string="Invoice from Delivery",
        help="Indicates whether the invoice should be created from the delivery order.",
        default=False,
    )

    def copy(self, default=None):
        if default is None:
            default = {}
        default.update({
            'td_invoice_from_delivery': False,
        })
        return super().copy(default=default)
    