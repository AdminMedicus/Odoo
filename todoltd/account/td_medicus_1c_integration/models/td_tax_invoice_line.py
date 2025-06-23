from odoo import fields, models, api


class TdTaxInvoiceLine(models.Model):
    _name = 'td.tax.invoice.line'

    td_invoice_id = fields.Many2one(
        comodel_name='td.tax.invoice'
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        required=True,
        string="Product Invoice"
    )
    name = fields.Char(
        string="Description"
    )
    lot_ids = fields.Many2many(
        comodel_name='stock.lot'
    )
    uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed',
        compute='_compute_product_id',
        readonly=False
    )
    quantity = fields.Float(
        default=1
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        related='product_id.uom_id'
    )
    price_with_out_vat = fields.Float()
    sum_price_with_out_vat = fields.Float()
    vat_id = fields.Many2one(
        comodel_name='account.tax',
        related='td_invoice_id.tax_guide'
    )
    vat_price = fields.Float()
    price_with_vat = fields.Float()

    @api.onchange('product_id', 'lot_ids', 'vat_id', 'quantity')
    @api.depends('product_id', 'lot_ids', 'vat_id', 'quantity')
    def _compute_product_id(self):
        for line in self:
            product = line.product_id
            if product:
                line.name = product.description

                if not line.price_with_out_vat:
                    line.price_with_out_vat = product.list_price

                line.sum_price_with_out_vat = (
                    line.price_with_out_vat * line.quantity
                )
                if line.vat_id:
                    amount_type = line.vat_id.amount_type
                    if amount_type == 'percent':
                        line.vat_price = (
                            line.sum_price_with_out_vat * line.vat_id.amount
                        ) / 100
                    else:
                        line.vat_price = line.vat_id.amount

                line.price_with_vat = (
                    line.sum_price_with_out_vat + line.vat_price
                )

                if line.lot_ids:
                    line.uktzed_code_id = (
                        line.lot_ids[0].td_uktzed_code_id.id or False
                    )
                if not line.uktzed_code_id:
                    if product.td_uktzed_code_id:
                        line.uktzed_code_id = product.td_uktzed_code_id.id
                    else:
                        line.uktzed_code_id = False
