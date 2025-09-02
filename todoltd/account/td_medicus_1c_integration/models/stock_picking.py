from odoo import models, fields, api, _
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
        selection_add=[('import', 'Import data to 1C')],
    )

    picking_code = fields.Boolean(
        compute="_compute_picking_code"
    )

    td_supplier_document = fields.Char()
    td_date_supplier_document = fields.Date()

    td_amount_origin_currency = fields.Float(
        compute="_compute_total_amounts"
    )
    td_total_without_tax = fields.Float(
        compute="_compute_total_amounts"
    )
    td_total_tax = fields.Float(
        compute="_compute_total_amounts"
    )

    def td_button_send_data_to_one_c(self):
        pass

    @api.depends('move_ids_without_package')
    def _compute_total_amounts(self):
        for rec in self:
            lines = rec.move_ids_without_package
            rec.td_amount_origin_currency = sum(lines.mapped('td_price_subtotal')) or 0
            rec.td_total_without_tax = sum(lines.mapped('td_price_subtotal')) or 0
            rec.td_total_tax = sum(lines.mapped('td_taxes_price')) or 0

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
                'name': 'TD Serial Auto Name',
                'code': code,
                'implementation': 'no_gap',
                'use_date_range': False,
                'prefix': 'SN-',
                'padding': 6,
            })
        return seq

    def _next_daily_lot_name(self, for_date=None):
        self.ensure_one()
        if not for_date:
            for_date = fields.Date.context_today(self)

        seq = self._ensure_sequence('td.lot.daily', 'TD daily lot sequence', for_date)

        base = seq.with_context(ir_sequence_date=for_date).next_by_id(sequence_date=for_date)

        suffix_parts = []
        if getattr(self, 'td_is_import', False):
            suffix_parts.append('IMPORT')
        if getattr(self, 'td_type_of_trade', False) == 'res_storage':
            suffix_parts.append('OX')

        if suffix_parts:
            return f"{base}/{'/'.join(suffix_parts)}"
        return base

    def _next_daily_serial_ref(self, for_date):
        self.ensure_one()
        if not for_date:
            for_date = fields.Date.context_today(self)

        seq = self._ensure_sequence(
            'td.serial.daily',
            'TD daily serial ref sequence',
            for_date
        )

        base = seq.with_context(ir_sequence_date=for_date).next_by_id()

        suffix_parts = []
        if getattr(self, 'td_is_import', False):
            suffix_parts.append('IMPORT')
        if getattr(self, 'td_type_of_trade', False) == 'res_storage':
            suffix_parts.append('OX')

        if suffix_parts:
            return f"{base}/{'/'.join(suffix_parts)}"
        return base

    def _next_serial_auto_name(self):
        seq = self._ensure_serial_auto_seq()
        return seq.next_by_id()

    # ---------------- helpers ----------------
    def _find_lot(self, LotModel, name, product, company_id):
        domain = [('name', '=', name), ('product_id', '=', product.id)]
        if company_id:
            domain.append(('company_id', '=', company_id))
        else:
            domain.append(('company_id', '=', False))
        return LotModel.search(domain, limit=1)

    def _create_or_retry_unique_lot(self, LotModel, name_getter, product, company_id, ref_getter,
                                    allow_use_existing=False):
        """
        Create a lot with a unique name for (product, company).
        - name_getter: callable() -> candidate name
        - ref_getter: callable(name) -> ref_value for a given name
        - allow_use_existing: if True and an existing lot with the same name is found,
          return it (and update ref).
        """
        for attempt in range(MAX_ATTEMPTS):
            name = name_getter()
            ref_value = ref_getter(name)
            existing = self._find_lot(LotModel, name, product, company_id)
            if existing:
                if allow_use_existing:
                    existing.write({'ref': ref_value})
                    return existing
                continue
            try:
                lot = LotModel.create({
                    'name': name,
                    'ref': ref_value,
                    'product_id': product.id,
                    'company_id': company_id,
                })
                return lot
            except Exception as e:
                msg = str(e).lower()
                if 'unique' in msg or 'duplicate' in msg or 'already exists' in msg:
                    continue
                raise
        raise UserError(_("Failed to generate a unique lot name for item %s after %s attempts.") %
                        (product.display_name, MAX_ATTEMPTS))

    def _create_lot_ids_for_move(self):
        Lot = self.env['stock.lot']
        today = fields.Date.context_today(self)

        for picking in self:
            company_id = picking.company_id.id if picking.company_id else False

            # --- PARTS (tracking == 'lot') ---
            processed_ml_ids = set()
            for ml in picking.move_line_ids.filtered(lambda l: l.product_id and l.product_id.tracking == 'lot'):
                if ml.id in processed_ml_ids:
                    continue

                def lot_name_getter():
                    return self._next_daily_lot_name(today)

                if ml.lot_id:
                    ml.lot_id.ref = lot_name_getter()
                    processed_ml_ids.add(ml.id)
                    continue

                lot = self._create_or_retry_unique_lot(
                    LotModel=Lot,
                    name_getter=lot_name_getter,
                    product=ml.product_id,
                    company_id=company_id,
                    ref_getter=lambda name: name,
                    allow_use_existing=False
                )
                ml.lot_id = lot.id
                processed_ml_ids.add(ml.id)

    def _assign_serial_ref(self):
        today = fields.Date.context_today(self)
        for picking in self:
            # --- SERIALS (tracking == 'serial') ---
            for move in picking.move_ids:
                product = move.product_id
                if not product or product.tracking != 'serial':
                    continue

                for ml in move.move_line_ids.filtered(lambda l: l.lot_id):
                    ref_val = self._next_daily_serial_ref(today)
                    try:
                        ml.lot_id.write({'ref': ref_val})
                    except Exception:
                        pass



    def button_validate(self):
        # if not self.td_is_import:

        res = super().button_validate()

        self._assign_serial_ref()
        self._create_lot_ids_for_move()

        for picking in self:
            for move in picking.move_ids:

                for lot in move.lot_ids:
                    uktzed_line = move.move_line_ids.filtered(lambda lin: lin.lot_id.id == lot.id)
                    move.lot_ids.write({
                        'td_uktzed_code_id': uktzed_line.td_uktzed_code_id.id if uktzed_line else False
                    })
                    move.td_uktzed_code_id = uktzed_line.td_uktzed_code_id.id if uktzed_line else False
        return res
        # return False