from odoo import _, api, fields, models
from odoo.tools import float_round


class TdTaxInvoiceLine(models.Model):
    _name = 'td.tax.invoice.line'
    _description = 'TdTaxInvoiceLine'

    corr_line_number = fields.Integer(
        string="Correction Line Number"
    )
    invoice_currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='invoice_line_id.currency_id',
        required=True,
        string='Invoice Currency'
    )
    invoice_line_id = fields.Many2one(
        comodel_name='account.move.line'
    )
    invoice_price = fields.Float(
        related='invoice_line_id.price_unit',
        string='Invoice Price'
    )
    invoice_price_subtotal = fields.Monetary(
        currency_field='invoice_currency_id',
        related='invoice_line_id.price_subtotal',
        string='Invoice Subtotal')
    invoice_quantity = fields.Float(
        related='invoice_line_id.quantity',
        string="Invoice Quantity"
    )
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        compute='_compute_lot_ids'
    )
    name = fields.Text(
        related='product_id.description_sale',
        string='Description'
    )
    price_with_out_vat = fields.Float()
    product_id = fields.Many2one(
        comodel_name='product.product',
        required=True,
        string='Product Invoice'
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        related='product_id.uom_id'
    )
    quantity = fields.Float(
        default=1,
        digits=(16, 5),
        string='Quantity'
    )
    sale_order_currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='td_sale_order_line_id.currency_id',
        required=True,
        string='Sale Order Currency'
    )
    sale_order_price = fields.Float(
        related='td_sale_order_line_id.price_unit',
        string='Sale Order Price'
    )
    sale_order_price_subtotal = fields.Monetary(
        currency_field='sale_order_currency_id',
        related='td_sale_order_line_id.price_subtotal',
        string='Sale Order Subtotal')
    sale_order_quantity = fields.Float(
        related='td_sale_order_line_id.product_uom_qty',
        string="Sale Order Quantity"
    )
    seq_line_number = fields.Integer(
        compute="_compute_line_number",
        store=True,
        string="№"
    )
    sum_price_with_out_vat = fields.Float()
    sum_price_with_vat = fields.Float()
    sum_vat_price = fields.Float()
    td_invoice_id = fields.Many2one(
        comodel_name='td.tax.invoice'
    )
    td_sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line'
    )
    uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed',
        compute='_compute_product_id',
        readonly=False
    )
    vat_id = fields.Many2one(
        comodel_name='account.tax',
        related='td_invoice_id.tax_guide_id'
    )
    vat_price = fields.Float()
    vat_type = fields.Selection(
        related='vat_id.price_include_override'
    )

    @api.depends('td_invoice_id', 'td_invoice_id.td_invoice_line_ids')
    def _compute_line_number(self):
        for record in self:
            if record.td_invoice_id:
                lines = record.td_invoice_id.td_invoice_line_ids
                for idx, line in enumerate(lines, start=1):
                    line.seq_line_number = idx
            else:
                record.seq_line_number = 1

    @api.depends('invoice_line_id')
    def _compute_lot_ids(self):
        for rec in self:
            if rec.td_invoice_id.invoice_type == 'regular':
                line = rec.invoice_line_id
                if line and line.td_order_line_id:
                    records = self.env['stock.move'].search([
                        ('sale_line_id', '=',
                         rec.invoice_line_id.td_order_line_id.id)
                    ])
                    outgoing_record = records.filtered(
                        lambda pick: (
                            pick.picking_id
                            and pick.picking_id.picking_type_code == "outgoing"
                        )
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

    @api.depends('product_id', 'lot_ids', 'vat_id', 'quantity')
    def _compute_product_id(self):
        for line in self:
            product = line.product_id
            if product:
                line.name = product.description
                rounding = line.td_invoice_id.company_id.currency_id.rounding

                if line.vat_type == 'tax_included':
                    tax_rate = line.vat_id.amount / 100
                    price_excluded = line.invoice_price / (1 + tax_rate)

                    line.price_with_out_vat = float_round(
                        price_excluded,
                        precision_rounding=rounding
                    )
                    line.vat_price = (
                        line.invoice_price - line.price_with_out_vat
                    )
                    line.sum_vat_price = float_round(
                        line.vat_price * line.quantity,
                        precision_rounding=rounding
                    )
                    line.sum_price_with_out_vat = float_round(
                        line.price_with_out_vat * line.quantity,
                        precision_rounding=rounding
                    )
                    line.sum_price_with_vat = (
                        line.sum_price_with_out_vat + line.sum_vat_price
                    )

                elif line.vat_type == 'tax_excluded':
                    tax_rate = line.vat_id.amount / 100
                    vat_amount = line.invoice_price * tax_rate

                    line.price_with_out_vat = line.invoice_price
                    line.vat_price = float_round(
                        vat_amount,
                        precision_rounding=rounding
                    )
                    line.sum_vat_price = float_round(
                        line.vat_price * line.quantity,
                        precision_rounding=rounding
                    )
                    line.sum_price_with_out_vat = float_round(
                        line.price_with_out_vat * line.quantity,
                        precision_rounding=rounding
                    )
                    line.sum_price_with_vat = (
                        line.sum_price_with_out_vat + line.sum_vat_price
                    )

                if line.lot_ids:
                    line.uktzed_code_id = (
                        line.lot_ids[0].td_uktzed_code_id.id or False
                    )
                if not line.uktzed_code_id:
                    line.uktzed_code_id = (
                        product.td_uktzed_code_id.id
                        if product.td_uktzed_code_id
                        else False
                    )