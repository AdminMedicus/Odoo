from odoo import fields, models, api


class TdTaxInvoiceLine(models.Model):
    _name = 'td.tax.invoice.line'
    _description = 'TdTaxInvoiceLine'

    td_invoice_id = fields.Many2one(
        comodel_name='td.tax.invoice'
    )
    td_sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line'
    )
    seq_line_number = fields.Integer(
        string="№",
        compute="_compute_line_number",
        store=True
    )
    invoice_line_id = fields.Many2one(
        comodel_name='account.move.line'
    )
    corr_line_number = fields.Integer(
        string="Correction Line Number"
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        required=True,
        string='Product Invoice'
    )
    name = fields.Text(
        string='Description',
        related='product_id.description_sale'
    )
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        compute='_compute_lot_ids'
    )
    uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed',
        compute='_compute_product_id',
        readonly=False
    )
    quantity = fields.Float(
        default=1,
        digits=(16, 5),
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        related='product_id.uom_id'
    )

    # price_with_out_vat = fields.Float()
    # sum_price_with_out_vat = fields.Float()
    vat_id = fields.Many2one(
        comodel_name='account.tax',
        related='td_invoice_id.tax_guide_id'
    )
    vat_type = fields.Selection(
        related='vat_id.price_include_override'
    )
    # vat_price = fields.Float()
    # price_with_vat = fields.Float()


    price_with_out_vat = fields.Float()
    sum_price_with_out_vat = fields.Float()

    vat_price = fields.Float()
    sum_vat_price = fields.Float()
    sum_price_with_vat = fields.Float()


    # SaleOrder fields
    sale_order_price = fields.Float(
        related='td_sale_order_line_id.price_unit'
    )
    sale_order_quantity = fields.Float(
        related='td_sale_order_line_id.product_uom_qty'
    )
    sale_order_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        related='td_sale_order_line_id.currency_id',
        default=lambda self: self.env.company.currency_id
    )
    sale_order_price_subtotal = fields.Monetary(
        related='td_sale_order_line_id.price_subtotal',
        currency_field='sale_order_currency_id',
    )

    # Invoice fields

    invoice_price = fields.Float(
        related='invoice_line_id.price_unit'
    )
    invoice_quantity = fields.Float(
        related='invoice_line_id.quantity'
    )
    invoice_currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        required=True,
        related='invoice_line_id.currency_id',
        default=lambda self: self.env.company.currency_id
    )
    invoice_price_subtotal = fields.Monetary(
        related='invoice_line_id.price_subtotal',
        currency_field='invoice_currency_id',
    )

    @api.depends('invoice_line_id')
    def _compute_lot_ids(self):
        for rec in self:
            if rec.td_invoice_id.invoice_type == 'regular':
                if rec.invoice_line_id and rec.invoice_line_id.td_order_line_id:
                    records = self.env['stock.move'].search([
                        ('sale_line_id', '=',
                         rec.invoice_line_id.td_order_line_id.id)
                    ])
                    outgoing_record = records.filtered(
                        lambda pick: pick.picking_id and pick.picking_id.picking_type_code == 'outgoing'
                    )
                    if outgoing_record:
                        rec.lot_ids = [(6, 0, [
                            lot.id for lot in outgoing_record[0].lot_ids
                        ])]
                    else:
                        rec.lot_ids = False
                else:
                    rec.lot_ids = False
            else:
                rec.lot_ids = False

    @api.depends('td_invoice_id', 'td_invoice_id.td_invoice_line_ids')
    def _compute_line_number(self):
        for record in self:
            if record.td_invoice_id:
                lines = record.td_invoice_id.td_invoice_line_ids
                for idx, line in enumerate(lines, start=1):
                    line.seq_line_number = idx
            else:
                record.seq_line_number = 1

    # @api.onchange('product_id', 'lot_ids', 'vat_id', 'quantity')
    @api.depends('product_id', 'lot_ids', 'vat_id', 'quantity')
    def _compute_product_id(self):
        for line in self:
            product = line.product_id
            if product:
                line.name = product.description

                if line.vat_type == 'tax_included':
                    tax_rate = line.vat_id.amount / 100
                    price_excluded = line.invoice_price / (1 + tax_rate)

                    line.price_with_out_vat = round(price_excluded, 2)
                    line.vat_price = line.invoice_price - line.price_with_out_vat
                    line.sum_vat_price = line.vat_price * line.invoice_quantity
                    line.sum_price_with_out_vat = line.price_with_out_vat * line.invoice_quantity
                    line.sum_price_with_vat = line.sum_price_with_out_vat + line.sum_vat_price

                elif line.vat_type == 'tax_excluded':
                    tax_rate = line.vat_id.amount / 100
                    price_excluded = line.invoice_price * tax_rate

                    line.price_with_out_vat = line.invoice_price
                    line.vat_price = round(price_excluded, 2)
                    line.sum_vat_price = line.vat_price * line.invoice_quantity
                    line.sum_price_with_out_vat = line.price_with_out_vat * line.invoice_quantity
                    line.sum_price_with_vat = line.sum_price_with_out_vat + line.sum_vat_price

                if line.lot_ids:
                    line.uktzed_code_id = (
                        line.lot_ids[0].td_uktzed_code_id.id or False
                    )
                if not line.uktzed_code_id:
                    if product.td_uktzed_code_id:
                        line.uktzed_code_id = product.td_uktzed_code_id.id
                    else:
                        line.uktzed_code_id = False
