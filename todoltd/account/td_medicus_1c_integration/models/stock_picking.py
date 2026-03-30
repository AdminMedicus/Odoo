from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError

MAX_ATTEMPTS = 10

class StockPicking(models.Model):
    _inherit = "stock.picking"

    td_currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='purchase_id.currency_id'
    )

    td_currency_rate = fields.Float(
        string="Currency Rate",
        digits=(12, 6),
        compute='_compute_currency_id_set_rate',
        readonly=False,
        store=True
    )

    td_type_of_trade = fields.Selection(
        [
            ('prepayment', 'Prepayment'),
            ('credit', 'Credit'),
            ('res_storage', 'Responsible Storage'),
        ], default='prepayment',
        related='purchase_id.td_type_of_trade'
    )

    td_is_import = fields.Boolean(
        string="Import",
        default=False,
        related='purchase_id.td_is_import'
    )

    state = fields.Selection(
        selection_add=[('import', 'Expects to spread costs over GTD')],
    )

    picking_code = fields.Boolean(
        compute="_compute_picking_code"
    )

    td_supplier_document = fields.Char()
    td_date_supplier_document = fields.Date()

    td_company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
        store=True
    )

    td_amount_origin_currency = fields.Monetary(
        compute="_compute_total_amounts",
        currency_field="td_currency_id",
    )
    td_total_without_tax = fields.Monetary(
        compute="_compute_total_amounts",
        currency_field="td_company_currency_id",
    )
    td_total_tax = fields.Monetary(
        compute="_compute_total_amounts",
        currency_field="td_company_currency_id",
    )
    td_total_amount = fields.Monetary(
        compute='_compute_td_total_amount',
        currency_field="td_company_currency_id",
    )

    td_vendor_bill_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="td_picking_id",
        string="Vendor Bills",
        readonly=True,
    )

    def td_button_send_data_to_one_c(self):
        for picking in self:
            if picking.picking_type_code != "incoming":
                raise UserError(_("This action is only available for receipts."))
            if not picking.td_is_import:
                raise UserError(_("This action is only available for import receipts."))
            if picking.state in ("done", "cancel"):
                raise UserError(_("Unable to perform action for completed/canceled document."))
            if not picking.move_ids_without_package:
                raise UserError(_("Add at least one item to the shipment."))

            if picking.state != "import":
                picking.write({"state": "import"})

            picking.message_post(
                body=_("Prepared. The document has been queued for exchange "
                       "with 1C for posting expenses from the customs declaration.")
            )

        return True

    @api.depends(
        'move_ids_without_package',
        'move_ids_without_package.quantity',
        'move_ids_without_package.td_price_unit',
        'move_ids_without_package.td_price_subtotal',
        'move_ids_without_package.td_taxes_price',
        'sale_id',
        'sale_id.amount_untaxed',
        'sale_id.amount_tax',
        'sale_id.amount_total',
        'td_currency_rate',
        'td_is_import',
    )
    def _compute_total_amounts(self):
        for rec in self:
            if rec.sale_id:
                rec.td_total_without_tax = rec.sale_id.amount_untaxed
                rec.td_total_tax = rec.sale_id.amount_tax
                rec.td_amount_origin_currency = rec.sale_id.amount_total
            else:
                lines = rec.move_ids_without_package
                rec.td_total_tax = sum(lines.mapped('td_taxes_price')) or 0.0

                if rec.td_is_import:
                    amount_origin_currency = sum(
                        line._td_get_origin_amount_total()
                        for line in lines
                    )
                    total_without_tax = sum(
                        line._td_get_company_amount_untaxed_total()
                        for line in lines
                    )

                    rec.td_amount_origin_currency = amount_origin_currency
                    rec.td_total_without_tax = total_without_tax
                else:
                    rec.td_total_without_tax = sum(lines.mapped('td_price_subtotal')) or 0.0
                    rec.td_amount_origin_currency = rec.td_total_without_tax + rec.td_total_tax

            rec.td_total_amount = rec.td_total_without_tax + rec.td_total_tax

    @api.depends('picking_type_id')
    def _compute_picking_code(self):
        for rec in self:
            rec.picking_code = True
            if rec.picking_type_id and rec.picking_type_id.code:
                if rec.picking_type_id.code == 'incoming':
                    rec.picking_code = False

    @api.depends("td_currency_id")
    def _compute_currency_id_set_rate(self):
        for record in self:
            if not record.td_currency_id:
                record.td_currency_rate = 1.0
                continue

            company_currency = record.company_id.currency_id
            if record.td_currency_id == company_currency:
                record.td_currency_rate = 1.0
                continue

            today = fields.Date.context_today(record)
            rate = self.env["res.currency.rate"].search(
                [
                    ("currency_id", "=", record.td_currency_id.id),
                    ("name", "<=", today),
                ],
                order="name desc",
                limit=1,
            )

            if rate:
                record.td_currency_rate = rate.inverse_company_rate
            else:
                record.td_currency_rate = 1.0

    def _ensure_sequence(self, code, name, for_date, prefix='%(day)s.%(month)s.%(year)s/'):
        Seq = self.env['ir.sequence'].sudo()
        seq = Seq.search([('code', '=', code)], limit=1)
        if not seq:
            seq = Seq.create({
                'name': name,
                'code': code,
                'implementation': 'no_gap',
                'use_date_range': True,
                'prefix': prefix,
                'padding': 2,
            })

        dt = for_date or self._context.get('ir_sequence_date', fields.Date.today())
        seq_date = self.env['ir.sequence.date_range'].search(
            [('sequence_id', '=', seq.id), ('date_from', '<=', dt), ('date_to', '>=', dt)], limit=1)

        if seq_date and seq_date.date_from != seq_date.date_to:
            seq_date.unlink()

        seq_date = self.env['ir.sequence.date_range'].search(
            [('sequence_id', '=', seq.id), ('date_from', '=', dt), ('date_to', '=', dt)], limit=1)
        if not seq_date:
            self.env['ir.sequence.date_range'].create({
                'sequence_id': seq.id,
                'date_from': dt,
                'date_to': dt,
                'number_next': 1,
            })

        return seq

    def _ensure_serial_auto_seq(self):
        Seq = self.env['ir.sequence'].sudo()
        code = 'td.serial.auto'
        seq = Seq.search([('code', '=', code)], limit=1)
        if not seq:
            seq = Seq.create({
                'name': 'Stock Lot Auto Sequence',
                'code': code,
                'implementation': 'no_gap',
                'prefix': '',
                'padding': 4,
            })
        return seq

    def _compute_td_total_amount(self):
        for rec in self:
            rec.td_total_amount = rec.td_total_without_tax + rec.td_total_tax
