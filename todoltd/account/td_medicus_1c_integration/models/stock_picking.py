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
        stroe=True
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

    def td_button_send_data_to_one_c(self):
        pass

    @api.depends('td_currency_id')
    def _compute_currency_id_set_rate(self):
        for record in self:
            if not record.td_currency_id:
                record.td_currency_rate = 1.0
                continue

            company_currency = record.company_id.currency_id
            if record.td_currency_id == company_currency:
                record.td_currency_rate = 1.0
                continue

            # rate = self.env['res.currency.rate'].search(
            #     [('currency_id', '=', record.td_currency_id.id)],
            #     order='name desc',
            #     limit=1
            # )

            if record.td_currency_id:
                record.td_currency_rate = record.td_currency_id.rate
            else:
                record.td_currency_rate = 1.0

    def _ensure_daily_sequence(self, code, name, prefix='%(day)s.%(month)s.%(year)s/'):
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

    def _next_daily_lot_name(self, for_date):
        seq = self._ensure_daily_sequence('td.lot.daily', 'TD daily lot sequence')
        return seq.next_by_id(sequence_date=for_date)

    def _next_daily_serial_ref(self, for_date):
        seq = self._ensure_daily_sequence('td.serial.daily', 'TD daily serial ref sequence')
        return seq.next_by_id(sequence_date=for_date)

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
        SML = self.env['stock.move.line']
        today = fields.Date.context_today(self)

        for picking in self:
            company_id = picking.company_id.id if picking.company_id else False

            # --- PARTS (tracking == 'lot') ---
            processed_ml_ids = set()
            for ml in picking.move_line_ids.filtered(lambda l: l.product_id and l.product_id.tracking == 'lot'):
                if ml.id in processed_ml_ids:
                    continue
                if ml.lot_id:
                    processed_ml_ids.add(ml.id)
                    continue

                def lot_name_getter():
                    return self._next_daily_lot_name(today)

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

            # --- SERIALS (tracking == 'serial') ---
            for move in picking.move_ids:
                product = move.product_id
                if not product or product.tracking != 'serial':
                    continue

                qty_done_total = sum(move.move_line_ids.mapped('qty_done'))
                planned_total = sum(move.move_line_ids.mapped('quantity')) or getattr(move, 'quantity', 0)
                target_qty = int(qty_done_total) if qty_done_total else int(planned_total)
                if target_qty <= 0:
                    continue

                def serial_ref_getter_unused(name_unused):
                    return self._next_daily_serial_ref(today)

                for ml in move.move_line_ids.filtered(lambda l: l.lot_id):
                    ref_val = serial_ref_getter_unused(None)
                    try:
                        ml.lot_id.write({'ref': ref_val})
                    except Exception:
                        pass

                for ml in move.move_line_ids.filtered(lambda l: not l.lot_id):
                    line_qty = int(ml.qty_done) if ml.qty_done else int(ml.quantity or 0)
                    if line_qty <= 0:
                        continue

                    user_provided_name = getattr(ml, 'lot_name', False) or False

                    first_piece = 1
                    if ml.qty_done:
                        ml.qty_done = first_piece
                    else:
                        ml.quantity = first_piece

                    ref_val = serial_ref_getter_unused(None)

                    if user_provided_name:
                        lot = self._find_lot(Lot, user_provided_name, product, company_id)
                        if lot:
                            lot.write({'ref': ref_val})
                        else:
                            lot = self._create_or_retry_unique_lot(
                                LotModel=Lot,
                                name_getter=lambda: user_provided_name,
                                product=product,
                                company_id=company_id,
                                ref_getter=lambda name: ref_val,
                                allow_use_existing=True
                            )
                    else:
                        lot = self._create_or_retry_unique_lot(
                            LotModel=Lot,
                            name_getter=lambda: self._next_serial_auto_name(),
                            product=product,
                            company_id=company_id,
                            ref_getter=lambda name: ref_val,
                            allow_use_existing=False
                        )
                    ml.lot_id = lot.id

                    remainder = line_qty - first_piece
                    for _ in range(remainder):
                        ref_val = serial_ref_getter_unused(None)
                        lot = self._create_or_retry_unique_lot(
                            LotModel=Lot,
                            name_getter=lambda: self._next_serial_auto_name(),
                            product=product,
                            company_id=company_id,
                            ref_getter=lambda name: ref_val,
                            allow_use_existing=False
                        )

                        puom_id = False
                        if getattr(move, 'product_uom', False):
                            puom_id = move.product_uom.id
                        elif getattr(move, 'product_uom_id', False):
                            puom_id = move.product_uom_id.id

                        SML.create({
                            'move_id': move.id,
                            'picking_id': picking.id,
                            'product_id': product.id,
                            'product_uom_id': puom_id,
                            'location_id': move.location_id.id,
                            'location_dest_id': move.location_dest_id.id,
                            'qty_done': 1 if qty_done_total else 0,
                            'quantity': 0 if qty_done_total else 1,
                            'lot_id': lot.id,
                        })

    def button_validate(self):
        if not self.td_is_import:
            self._create_lot_ids_for_move()

            res = super().button_validate()

            for picking in self:
                for move in picking.move_ids:

                    for lot in move.lot_ids:
                        uktzed_line = move.move_line_ids.filtered(lambda lin: lin.lot_id.id == lot.id)
                        move.lot_ids.write({
                            'td_uktzed_code_id': uktzed_line.td_uktzed_code_id.id if uktzed_line else False
                        })
                        move.td_uktzed_code_id = uktzed_line.td_uktzed_code_id.id if uktzed_line else False
            return res
        return False