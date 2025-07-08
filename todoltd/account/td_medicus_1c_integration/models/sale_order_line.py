from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    td_invoice_id = fields.Many2one(
        comodel_name='account.move.line'
    )

    @api.onchange('tax_id')
    def _onchange_tax_id_td(self):
        for line in self:
            if line.order_id.td_tax_guide_id.id != line.tax_id.id:
                raise ValidationError(
                    _("You are trying to add products with different VAT rates")
                )
