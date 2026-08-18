from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare

MAX_ATTEMPTS = 10

class StockPicking(models.Model):
    _inherit = "stock.picking"

    td_currency_id = fields.Many2one(
        comodel_name='res.currency',
        compute='_compute_td_currency_id',
        readonly=False,
        store=True,
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
        ],
        string="Type of Trade",
        default='prepayment',
        readonly=False,
        store=True,
    )

    td_is_import = fields.Boolean(
        string="Import",
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
        compute='_compute_total_amounts',
        currency_field="td_company_currency_id",
    )

    td_vendor_bill_ids = fields.One2many(
        comodel_name="account.move",
        inverse_name="td_picking_id",
        string="Vendor Bills",
        readonly=True,
    )

    td_agreement_id = fields.Many2one(
        comodel_name="td.agreement",
        string="Agreement",
        ondelete="restrict",
        tracking=True,
        domain='[("partner_id", "=?", partner_id)]',
    )

    td_auto_create_purchase_on_validate = fields.Boolean(
        related="picking_type_id.td_auto_create_purchase_on_validate",
        readonly=True,
    )

    td_is_goods_balance_of_act_res_st = fields.Boolean(
        related="picking_type_id.td_is_goods_balance_of_act_res_st",
        readonly=True,
    )

    def _td_get_receipt_lots(self):
        lots = self.env['stock.lot']

        for picking in self:
            lots |= picking.move_line_ids.mapped('lot_id')

            for move in picking.move_ids:
                if 'lot_ids' in move._fields:
                    lots |= move.lot_ids

                if 'td_lot_ids' in move._fields:
                    lots |= move.td_lot_ids

        return lots.filtered(lambda lot: lot and lot.product_id)

    def _td_invalidate_receipt_lot_qty_cache(self):
        lots = self._td_get_receipt_lots()
        if lots:
            lots.invalidate_recordset(['product_qty', 'td_available_qty'])

    @api.depends('purchase_id.currency_id', 'company_id.currency_id')
    def _compute_td_currency_id(self):
        for picking in self:
            picking.td_currency_id = (
                picking.purchase_id.currency_id
                or picking.company_id.currency_id
                or self.env.company.currency_id
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

            picking._td_prepare_import_lots_for_onec_exchange()

            if picking.state != "import":
                picking.write({"state": "import"})

            picking.message_post(
                body=_(
                    "Prepared. The document has been queued for exchange "
                    "with 1C for posting expenses from the customs declaration."
                )
            )

        return True

    @api.depends(
        'move_ids_without_package',
        'move_ids_without_package.quantity',
        'move_ids_without_package.td_price_unit',
        'move_ids_without_package.td_untaxed_price_unit',
        'move_ids_without_package.td_price_subtotal',
        'move_ids_without_package.td_price_total',
        'move_ids_without_package.td_taxes_price',
        'move_ids_without_package.td_customs_value_good',
        'move_ids_without_package.td_currency_rate',
        'td_currency_rate',
        'td_is_import',
        'sale_id.amount_total',
        'purchase_id.amount_total',
    )
    def _compute_total_amounts(self):
        for rec in self:
            lines = rec.move_ids_without_package
            order = rec.sale_id or rec.purchase_id

            if order:
                total_amount = order.amount_total
            else:
                total_amount = sum(
                    move._td_get_origin_amount_total()
                    if hasattr(move, '_td_get_origin_amount_total')
                    else (move.td_price_total or move.td_price_subtotal or 0.0)
                    for move in lines
                )

            if rec.td_is_import:
                rec.td_total_without_tax = sum(
                    move.td_customs_value_good
                    for move in lines
                )
            else:
                rec.td_total_without_tax = sum(
                    move._td_get_company_amount_untaxed_total()
                    if hasattr(move, '_td_get_company_amount_untaxed_total')
                    else (move.td_price_subtotal or 0.0)
                    for move in lines
                )

            rec.td_total_tax = sum(lines.mapped('td_taxes_price')) or 0.0
            rec.td_amount_origin_currency = total_amount
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
            [('sequence_id', '=', seq.id), ('date_from', '<=', dt), ('date_to', '>=', dt)],
            limit=1,
        )

        if seq_date and seq_date.date_from != seq_date.date_to:
            seq_date.unlink()

        seq_date = self.env['ir.sequence.date_range'].search(
            [('sequence_id', '=', seq.id), ('date_from', '=', dt), ('date_to', '=', dt)],
            limit=1,
        )
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

    # def _compute_td_total_amount(self):
    #     for rec in self:
    #         rec.td_total_amount = rec.td_total_without_tax + rec.td_total_tax

    def _next_daily_lot_name(self, for_date=None):
        self.ensure_one()
        if not for_date:
            for_date = fields.Date.context_today(self)

        seq = self._ensure_sequence(
            'td.lot.daily',
            'TD daily lot sequence',
            for_date,
        )

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
            for_date,
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

    def _td_set_done_qty_vals(self, vals, qty):
        """Set done quantity in move line vals for both old/new Odoo stock fields."""
        MoveLine = self.env['stock.move.line']
        if 'quantity' in MoveLine._fields:
            vals['quantity'] = qty
        if 'qty_done' in MoveLine._fields:
            vals['qty_done'] = qty
        return vals

    def _td_get_move_line_done_qty(self, move_line):
        if 'quantity' in move_line._fields:
            return move_line.quantity or 0.0

        if 'qty_done' in move_line._fields:
            return move_line.qty_done or 0.0

        return 0.0

    def _td_raise_missing_lot_name_error(self, move):
        raise UserError(_(
            'Заповніть партію/серію для товару "%(product)s" перед підтвердженням надходження.'
        ) % {
            'product': move.product_id.display_name,
        })

    def _td_validate_manual_lot_names_for_receipt(self):
        """Require manual lot/serial input for incoming tracked products.

        The module used to generate lots automatically before validation.
        This check intentionally blocks confirmation/preparation until the
        user enters lot_name manually or selects an existing lot_id.
        """
        for picking in self.filtered(
            lambda p: p.picking_type_code == 'incoming'
                      and p.state not in ('done', 'cancel')
        ):
            for move in picking.move_ids_without_package.filtered(
                lambda m: m.product_id and m.product_id.tracking != 'none'
            ):
                move_lines = move.move_line_ids.filtered(
                    lambda line: line.product_id == move.product_id
                )
                if not move_lines:
                    picking._td_raise_missing_lot_name_error(move)

                lines_with_qty = self.env['stock.move.line']
                for move_line in move_lines:
                    qty = picking._td_get_move_line_done_qty(move_line)
                    if qty:
                        lines_with_qty |= move_line
                        lot_name = (move_line.lot_name or '').strip() if 'lot_name' in move_line._fields else ''
                        if not move_line.lot_id and not lot_name:
                            picking._td_raise_missing_lot_name_error(move)

                        if move.product_id.tracking == 'serial' and abs(qty) != 1.0:
                            raise UserError(_(
                                'Для товару "%(product)s" із серійним обліком кожен серійний номер '
                                'має бути введений окремим рядком з кількістю 1.'
                            ) % {
                                'product': move.product_id.display_name,
                            })

                if not lines_with_qty:
                    picking._td_raise_missing_lot_name_error(move)

    def _td_get_or_create_manual_lot(self, lot_name, product, company_id):
        self.ensure_one()
        lot_name = (lot_name or '').strip()
        if not lot_name:
            raise UserError(_(
                'Заповніть партію/серію для товару "%(product)s".'
            ) % {'product': product.display_name})

        Lot = self.env['stock.lot'].sudo()
        lot = self._find_lot(Lot, lot_name, product, company_id)
        if lot:
            return lot

        return Lot.create({
            'name': lot_name,
            'ref': lot_name,
            'product_id': product.id,
            'company_id': company_id,
        })

    def _td_prepare_import_lots_for_onec_exchange(self):
        """Prepare manually entered lots/serials for import exchange.

        Import receipts are moved to the custom `import` state before the final
        stock validation, so 1C needs stable stock.lot records.  Unlike the old
        implementation, this method never generates lot names; it only creates
        stock.lot records from lot_name values entered by the user.
        """
        MoveLineModel = self.env['stock.move.line']

        for picking in self:
            picking._td_validate_manual_lot_names_for_receipt()
            company_id = picking.company_id.id if picking.company_id else False

            for move in picking.move_ids_without_package.filtered(
                lambda m: m.product_id and m.product_id.tracking != 'none'
            ):
                lots = self.env['stock.lot']
                kept_lines = MoveLineModel.browse()

                for move_line in move.move_line_ids.sorted('id'):
                    qty = picking._td_get_move_line_done_qty(move_line)
                    if not qty:
                        continue

                    lot = move_line.lot_id
                    if not lot:
                        lot = picking._td_get_or_create_manual_lot(
                            move_line.lot_name,
                            move.product_id,
                            company_id,
                        )
                        move_line.write({'lot_id': lot.id})

                    if not lot.ref:
                        lot.ref = lot.name

                    lots |= lot
                    kept_lines |= move_line

                # lot_ids/td_lot_ids are computed from move_line_ids.
                # Do not write them here, because their inverse logic may create
                # or resize move lines and can duplicate the received quantity.

    def _td_get_import_lock_move_lines(self, lot):
        self.ensure_one()
        return self.env['stock.move.line'].sudo().search([
            ('lot_id', '=', lot.id),
            ('product_id', '=', lot.product_id.id),
            ('picking_id.state', '=', 'import'),
            ('picking_id.picking_type_code', '=', 'incoming'),
            ('picking_id.company_id', '=', self.company_id.id),
        ])

    def _td_raise_serial_import_lock_error(self, lot, import_picking):
        raise UserError(_(
            'Неможливо підтвердити документ. Товар "%(product)s" із серійним номером "%(serial)s" наразі заблокований для реалізації. '
            'Серійний номер входить до складу надходження "%(picking)s", яке очікує рознесення витрат з ГТД '
            '(статус: Очікує рознесення витрат з ГТД). Реалізація можлива лише після завершення рознесення витрат '
            'по даному надходженню.'
        ) % {
            'product': lot.product_id.display_name,
            'serial': lot.name,
            'picking': import_picking.name,
        })

    def _td_check_import_realization_restrictions(self):
        for picking in self.filtered(lambda p: p.picking_type_code == 'outgoing' and p.state not in ('done', 'cancel')):
            qty_by_lot = {}
            move_lines = picking.move_line_ids.filtered(lambda ml: ml.lot_id and ml.product_id)

            for move_line in move_lines:
                lot = move_line.lot_id
                import_lines = picking._td_get_import_lock_move_lines(lot)
                if import_lines:
                    picking._td_raise_serial_import_lock_error(lot, import_lines[0].picking_id)

                qty_by_lot.setdefault(lot.id, {'lot': lot, 'qty': 0.0})
                qty_by_lot[lot.id]['qty'] += abs(move_line.quantity or 0.0)

            for move in picking.move_ids_without_package.filtered(
                    lambda m: m.product_id and m.product_id.tracking == 'lot' and m.lot_ids
            ):
                existing_qty = sum(
                    value['qty'] for value in qty_by_lot.values()
                    if value['lot'] in move.lot_ids
                )
                remaining_qty = max((move.quantity or 0.0) - existing_qty, 0.0)
                if remaining_qty and len(move.lot_ids) == 1:
                    lot = move.lot_ids[0]
                    qty_by_lot.setdefault(lot.id, {'lot': lot, 'qty': 0.0})
                    qty_by_lot[lot.id]['qty'] += remaining_qty

            for data in qty_by_lot.values():
                lot = data['lot']
                requested_qty = data['qty']
                available_qty = lot.td_available_qty

                if requested_qty > available_qty:
                    import_lines = picking._td_get_import_lock_move_lines(lot)
                    if import_lines:
                        picking._td_raise_serial_import_lock_error(lot, import_lines[0].picking_id)

                    raise UserError(_(
                        'Неможливо підтвердити документ. Товар "%(product)s" за партією/серією "%(lot)s" '
                        'недоступний для реалізації у потрібній кількості. Доступна кількість: %(available)s, '
                        'кількість у документі: %(requested)s.'
                    ) % {
                        'product': lot.product_id.display_name,
                        'lot': lot.name,
                        'available': available_qty,
                        'requested': requested_qty,
                    })

    # ---------------- helpers ----------------
    def _find_lot(self, LotModel, name, product, company_id):
        domain = [
            ('name', '=', name),
            ('product_id', '=', product.id),
        ]
        if company_id:
            domain.append(('company_id', '=', company_id))
        else:
            domain.append(('company_id', '=', False))
        return LotModel.search(domain, limit=1)

    def _create_or_retry_unique_lot(
            self,
            LotModel,
            name_getter,
            product,
            company_id,
            ref_getter,
            allow_use_existing=False,
    ):
        """
        Create a lot with a unique name for (product, company).

        Args:
            name_getter (callable): function -> candidate name.
            ref_getter (callable): function(name) -> ref_value
            for a given name.
            allow_use_existing (bool): if True and an existing lot with the
                same name is found, return it (and update ref).
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
                if "unique" in msg or "duplicate" in msg or "already exists" in msg:
                    continue
                raise

        raise UserError(_(
            "Failed to generate a unique lot name for item %s after %s attempts."
        ) % (product.display_name, MAX_ATTEMPTS))

    def _create_lot_ids_for_move(self):
        """Deprecated compatibility hook.

        Lot/serial records must be created from user-entered lot_name by the
        standard validation flow, not generated automatically by custom code.
        """
        self._td_validate_manual_lot_names_for_receipt()

    def _assign_serial_ref(self):
        today = fields.Date.context_today(self)
        for picking in self:
            # --- SERIALS (tracking == 'serial') ---
            for move in picking.move_ids:
                product = move.product_id
                if not product or product.tracking != 'serial':
                    continue

                for ml in move.move_line_ids.filtered(lambda m_l: m_l.lot_id):
                    ref_val = self._next_daily_serial_ref(today)
                    try:
                        ml.lot_id.write({'ref': ref_val})
                    except Exception:
                        pass

    def _td_get_purchase_journal(self, company):
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", company.id)],
            limit=1,
        )
        if not journal:
            raise UserError(
                _(
                    "No Purchase journal found for company %s"
                ) % company.display_name)
        return journal

    def _td_get_expense_account(self, product, company):
        account = (
                product.property_account_expense_id
                or product.categ_id.property_account_expense_categ_id
        )
        if not account:
            raise UserError(
                _("No expense account for product %s (company %s)")
                % (product.display_name, company.display_name)
            )
        return account

    def _td_get_move_done_qty(self, move):
        move_lines = move.move_line_ids
        if move_lines:
            if 'qty_done' in move_lines._fields:
                qty = sum(move_lines.mapped('qty_done'))
                if qty:
                    return qty
            if 'quantity' in move_lines._fields:
                qty = sum(move_lines.mapped('quantity'))
                if qty:
                    return qty
        return getattr(move, 'quantity', 0.0) or getattr(move, 'product_uom_qty', 0.0) or 0.0

    def _td_get_move_purchase_qty(self, move):
        return getattr(move, 'quantity', 0.0) or getattr(move, 'product_uom_qty', 0.0) or 0.0

    def _td_is_return_receipt(self):
        self.ensure_one()
        if getattr(self, 'return_id', False) or getattr(self, 'return_ids', False):
            return True
        return any(
            getattr(move, 'origin_returned_move_id', False)
            for move in self.move_ids_without_package
        )

    def _td_has_linked_purchase(self):
        self.ensure_one()
        if self.purchase_id:
            return True
        return bool(self.move_ids_without_package.mapped('purchase_line_id.order_id'))

    def _td_should_auto_create_purchase_on_validate(self):
        self.ensure_one()
        return all([
            self.picking_type_code == 'incoming',
            self.td_auto_create_purchase_on_validate,
            not self.origin,
            not self._td_has_linked_purchase(),
            not self._td_is_return_receipt(),
        ])

    def _td_get_purchase_currency(self):
        self.ensure_one()
        partner = self.partner_id
        partner_currency = (
            partner.property_purchase_currency_id
            if partner and 'property_purchase_currency_id' in partner._fields
            else False
        )
        return (
            partner_currency
            or self.company_id.currency_id
            or self.env.company.currency_id
        )

    def _td_prepare_auto_purchase_order_vals(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Vendor is required to create a Purchase Order automatically."))

        planned_date = fields.Datetime.now()
        PurchaseOrder = self.env['purchase.order']

        vals = {
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'currency_id': self._td_get_purchase_currency().id,
            'picking_type_id': self.picking_type_id.id,
            'partner_ref': self.td_supplier_document or False,
            'origin': self.name,
        }

        if 'date_approve' in PurchaseOrder._fields:
            vals['date_approve'] = planned_date
        if 'date_planned' in PurchaseOrder._fields:
            vals['date_planned'] = planned_date
        if 'td_agreement_id' in PurchaseOrder._fields:
            vals['td_agreement_id'] = self.td_agreement_id.id if self.td_agreement_id else False
        if 'td_type_of_trade' in PurchaseOrder._fields:
            vals['td_type_of_trade'] = self.td_type_of_trade or 'prepayment'

        return vals

    def _td_prepare_auto_purchase_order_line_vals(self, purchase_order, move):
        self.ensure_one()
        qty = self._td_get_move_purchase_qty(move)
        if not qty:
            raise UserError(_(
                'Quantity is required to create a Purchase Order line for product "%s".'
            ) % move.product_id.display_name)

        company = self.company_id
        taxes = move.product_id.supplier_taxes_id.filtered(
            lambda tax: not tax.company_id or tax.company_id == company
        )

        vals = {
            'order_id': purchase_order.id,
            'product_id': move.product_id.id,
            'name': move.name or move.product_id.display_name,
            'product_qty': qty,
            'product_uom': move.product_uom.id,
            'price_unit': move.td_price_unit or 0.0,
            'date_planned': fields.Datetime.now(),
        }

        if taxes:
            vals['taxes_id'] = [Command.set(taxes.ids)]
        else:
            vals['taxes_id'] = [Command.clear()]

        return vals

    # def _td_cancel_auto_generated_purchase_pickings(self, purchase_order):
    #     self.ensure_one()
    #     generated_pickings = purchase_order.picking_ids.filtered(lambda picking: picking.id != self.id)
    #     generated_pickings = generated_pickings.filtered(lambda picking: picking.state not in ('done', 'cancel'))
    #     if generated_pickings:
    #         generated_pickings.action_cancel()

    def _td_cancel_auto_generated_purchase_pickings(self, purchase_order):
        self.ensure_one()

        generated_pickings = purchase_order.picking_ids.filtered(
            lambda picking: picking.id != self.id
        )
        if not generated_pickings:
            return

        pickings_to_cancel = generated_pickings.filtered(
            lambda picking: picking.state not in ('done', 'cancel')
        )
        if pickings_to_cancel:
            pickings_to_cancel.action_cancel()

        # Current receipt is linked to generated PO manually.
        # purchase.order.button_confirm() creates its own technical receipt.
        # If we only cancel it, other integrations can still find 2 pickings
        # by purchase_id and fail with Expected singleton.
        pickings_to_unlink = generated_pickings.filtered(
            lambda picking: picking.state == 'cancel'
        )
        if pickings_to_unlink:
            pickings_to_unlink.unlink()

    def _td_sync_book_value_to_lots_from_moves(self):
        precision = self.env['decimal.precision'].precision_get('Product Price')

        for picking in self:
            for move in picking.move_ids:
                if not move.product_id:
                    continue

                new_price = move._td_get_lot_cost_for_sync()
                if new_price is None:
                    continue

                lots = move._td_get_lots_for_cost_sync()
                if not lots:
                    continue

                lots_to_update = lots.filtered(
                    lambda lot: float_compare(
                        lot.standart_price or 0.0,
                        new_price,
                        precision_digits=precision,
                    ) != 0
                )

                for lot in lots_to_update:
                    move._td_write_lot_cost(lot, new_price)

    def _td_link_receipt_to_purchase_order(self, purchase_order, move_line_pairs):
        self.ensure_one()
        write_vals = {'origin': purchase_order.name}
        if purchase_order.group_id:
            write_vals['group_id'] = purchase_order.group_id.id

        self.write(write_vals)

        for move, purchase_line in move_line_pairs:
            move_vals = {'purchase_line_id': purchase_line.id}
            if purchase_order.group_id:
                move_vals['group_id'] = purchase_order.group_id.id
            move.write(move_vals)

    def _td_create_purchase_order_from_receipt(self):
        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']

        for picking in self:
            if not picking._td_should_auto_create_purchase_on_validate():
                continue

            moves = picking.move_ids_without_package.filtered(lambda move: move.product_id)
            if not moves:
                raise UserError(_("Add at least one product line before validating the receipt."))

            purchase_order = PurchaseOrder.create(picking._td_prepare_auto_purchase_order_vals())
            move_line_pairs = []
            for move in moves:
                purchase_line = PurchaseOrderLine.create(
                    picking._td_prepare_auto_purchase_order_line_vals(purchase_order, move)
                )
                move_line_pairs.append((move, purchase_line))

            try:
                purchase_order.button_confirm()
            except Exception as error:
                raise UserError(_(
                    "Unable to confirm the automatically created Purchase Order. "
                    "Receipt validation was stopped. Error: %s"
                ) % error)

            picking._td_link_receipt_to_purchase_order(purchase_order, move_line_pairs)
            picking._td_cancel_auto_generated_purchase_pickings(purchase_order)

            picking.message_post(body=_(
                "Purchase Order %(purchase_order)s was created automatically from this receipt."
            ) % {'purchase_order': purchase_order.display_name})

    def _td_prepare_auto_lots_before_validate(self):
        """Backward-compatible hook.

        Lot/serial names are no longer generated automatically.  The hook now
        only validates that the user entered lot_name/lot_id manually.
        """
        self._td_validate_manual_lot_names_for_receipt()

    def _td_create_vendor_bill_from_receipt(self):
        AccountMove = self.env["account.move"]

        for picking in self:
            if picking.picking_type_id.code != "incoming":
                continue
            if picking.state != "done":
                continue

            existing = AccountMove.search([
                ("td_picking_id", "=", picking.id),
                ("move_type", "=", "in_invoice"),
                ("state", "!=", "cancel"),
            ], limit=1)
            if existing:
                continue

            moves = picking.move_ids_without_package.filtered(
                lambda m: m.product_id and m.purchase_line_id
                          and picking._td_get_move_done_qty(m) > 0
            )
            if not moves:
                continue

            purchase_orders = moves.mapped("purchase_line_id.order_id").filtered(lambda po: po)
            if not purchase_orders:
                continue

            if len(purchase_orders) > 1:
                raise UserError(
                    _("This receipt contains lines from multiple "
                      "Purchase Orders. Please split receipts "
                      "or adjust logic."))

            po = purchase_orders[0]
            company = picking.company_id
            journal = self._td_get_purchase_journal(company)

            invoice_vals = po._prepare_invoice()

            invoice_vals.update({
                "move_type": "in_invoice",
                "journal_id": journal.id,
                "td_picking_id": picking.id,
                "invoice_origin": picking.name,
            })

            if picking.td_supplier_document:
                invoice_vals["ref"] = picking.td_supplier_document
            if picking.td_date_supplier_document:
                invoice_vals["invoice_date"] = picking.td_date_supplier_document
                invoice_vals["date"] = picking.td_date_supplier_document

            line_cmds = []
            for move in moves:
                pol = move.purchase_line_id
                product = move.product_id

                taxes = getattr(pol, "taxes_id", self.env["account.tax"])
                account = self._td_get_expense_account(product, company)

                qty_done = picking._td_get_move_done_qty(move)

                line_vals = {
                    "product_id": product.id,
                    "name": pol.name or product.display_name,
                    "quantity": qty_done,
                    "price_unit": pol.price_unit,
                    "account_id": account.id,
                }

                if "product_uom_id" in self.env["account.move.line"]._fields:
                    line_vals["product_uom_id"] = move.product_uom.id
                elif "product_uom" in self.env["account.move.line"]._fields:
                    line_vals["product_uom"] = move.product_uom.id

                if taxes:
                    line_vals["tax_ids"] = [Command.set(taxes.ids)]

                if "purchase_line_id" in self.env["account.move.line"]._fields:
                    line_vals["purchase_line_id"] = pol.id

                line_cmds.append(Command.create(line_vals))

            invoice_vals["invoice_line_ids"] = line_cmds

            bill = AccountMove.create(invoice_vals)

            if bill.state != "posted":
                bill.action_post()

    # def button_validate(self):
    #     self._td_check_import_realization_restrictions()
    #     self._td_create_purchase_order_from_receipt()
    #     res = super().button_validate()
    #
    #     if not self.sale_id:
    #         self._assign_serial_ref()
    #         self._create_lot_ids_for_move()
    #
    #     for picking in self:
    #         for move in picking.move_ids:
    #             for lot in move.lot_ids:
    #                 uktzed_line = move.move_line_ids.filtered(lambda lin: lin.lot_id.id == lot.id)
    #                 move.lot_ids.write({
    #                     "td_uktzed_code_id": (uktzed_line.td_uktzed_code_id.id if uktzed_line else False)
    #                 })
    #                 move.td_uktzed_code_id = (uktzed_line.td_uktzed_code_id.id if uktzed_line else False)
    #
    #     self._td_create_vendor_bill_from_receipt()
    #     return res

    def button_validate(self):
        self._td_check_import_realization_restrictions()

        # 1. First create PO from manual receipt if needed.
        self._td_create_purchase_order_from_receipt()

        # 2. Do not auto-generate lot/serial names.  The user must fill
        # lot_name manually; standard Odoo validation will create the lot from
        # that value during super().button_validate().
        self._td_validate_manual_lot_names_for_receipt()

        res = super().button_validate()

        self._td_sync_book_value_to_lots_from_moves()
        self._td_invalidate_receipt_lot_qty_cache()

        if not self.sale_id:
            self._assign_serial_ref()

        for picking in self:
            for move in picking.move_ids:
                for lot in move.lot_ids:
                    uktzed_line = move.move_line_ids.filtered(
                        lambda lin: lin.lot_id.id == lot.id
                    )
                    move.lot_ids.write({
                        "td_uktzed_code_id": (
                            uktzed_line.td_uktzed_code_id.id if uktzed_line else False
                        )
                    })
                    move.td_uktzed_code_id = (
                        uktzed_line.td_uktzed_code_id.id if uktzed_line else False
                    )

        self.move_ids._td_sync_td_book_value_to_lots()
        self._td_create_vendor_bill_from_receipt()
        return res

    def _td_get_public_user(self):
        return self.env.ref("base.public_user", raise_if_not_found=False) or self.env["res.users"].browse(4)

    def _td_collect_created_lots(self):
        self.ensure_one()
        lots = self.move_line_ids.mapped("lot_id")
        return lots.filtered(lambda l: l and l.product_id)

    def _td_apply_lot_prices_and_create_svl(self, onec_doc_number, lot_prices, changed=False, chatter_message=None):
        self.ensure_one()

        if not self.td_is_import:
            raise UserError(_("This action is only available for import receipts (td_is_import)."))

        # 0) ensure done first -> lots + quants + moves стабільно існують
        if self.state != "done":
            try:
                ctx = dict(self.env.context, skip_backorder=True, skip_immediate=True)
                self.with_context(ctx).sudo().button_validate()
            except Exception as e:
                raise UserError(_("Unable to validate receipt to Done automatically. Error: %s") % (e,))

        # 1) parse incoming lot prices
        by_id = {}
        by_name = {}
        for item in (lot_prices or []):
            if not isinstance(item, dict):
                continue
            price = item.get("price", item.get("standart_price", item.get("standard_price")))
            if price is None:
                continue

            lot_id = item.get("lot_id")
            if lot_id:
                by_id[int(lot_id)] = float(price)
                continue

            lot_name = item.get("lot_name") or item.get("name")
            if lot_name:
                prod_id = item.get("product_id")
                default_code = item.get("product_default_code") or item.get("default_code")
                key = (str(lot_name).strip(), int(prod_id) if prod_id else None,
                       str(default_code).strip() if default_code else None)
                by_name[key] = float(price)

        lots = self._td_collect_created_lots()
        if not lots:
            raise UserError(_("No lots/serials found on this receipt."))

        # 2) Build reference tag required by TZ
        tag = f"{onec_doc_number}/1C" + ("/changed" if changed else "")

        # 3) chatter message from Public user
        if chatter_message:
            public_user = self._td_get_public_user()
            author_partner = public_user.partner_id
            self.message_post(
                body=chatter_message,
                author_id=author_partner.id,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

        SVL = self.env["stock.valuation.layer"].sudo()

        # 4) For each lot -> find move, update lot cost, create SVL linked to move+lot
        for lot in lots:
            # find new_price
            new_price = None
            if lot.id in by_id:
                new_price = by_id[lot.id]
            else:
                lot_name = (lot.name or "").strip()
                key1 = (lot_name, lot.product_id.id, None)
                key2 = (lot_name, None, (lot.product_id.default_code or "").strip() or None)
                key3 = (lot_name, None, None)
                for k in (key1, key2, key3):
                    if k in by_name:
                        new_price = by_name[k]
                        break

            # find related move via move lines
            related_move_lines = self.move_line_ids.filtered(
                lambda line: line.lot_id.id == lot.id
                             and line.product_id.id == lot.product_id.id
            )
            ml = related_move_lines[:1]
            move = ml.move_id if ml else False

            # If 1C updated td_book_value on stock.move, use it as the lot cost
            # even when the legacy lot_prices payload is empty.
            if new_price is None and move and move.td_book_value:
                new_price = move.td_book_value

            if new_price is None:
                continue

            old_price = getattr(lot, "standard_price", False) or getattr(lot, "standart_price", 0.0) or 0.0

            lot_vals = {}
            if 'standard_price' in lot._fields:
                lot_vals['standard_price'] = new_price
            if 'standart_price' in lot._fields:
                lot_vals['standart_price'] = new_price
            if lot_vals and float(new_price) != float(old_price):
                lot.sudo().write(lot_vals)

            receipt_qty = sum(
                self._td_get_move_line_done_qty(line)
                for line in related_move_lines
            )
            qty = receipt_qty or lot._td_get_internal_qty(company=self.company_id)
            if not qty:
                continue

            value_diff = (float(new_price) - float(old_price)) * float(qty)
            if abs(value_diff) < 1e-9:
                continue

            # IMPORTANT: SVL.reference is related to stock_move_id.reference in your system.
            # So we must write reference tag into move.reference and link SVL to that move.
            if move:
                old_ref = move.reference or ""
                # avoid duplication if method called twice
                if tag not in old_ref:
                    new_ref = tag if not old_ref else f"{old_ref} | {tag}"
                    move.sudo().write({"reference": new_ref})

            svl_vals = {
                "product_id": lot.product_id.id,
                "company_id": (self.company_id.id or lot.company_id.id),
                "quantity": 0.0,
                "value": value_diff,
                "unit_cost": float(new_price),
                "remaining_qty": 0.0,
                "remaining_value": 0.0,
                "description": _("1C GTD cost adjustment for lot %(lot)s") % {"lot": lot.name},
                "lot_id": lot.id,
            }
            if move:
                svl_vals["stock_move_id"] = move.id

            SVL.create(svl_vals)

        return tag

    # ---------------- Public methods called by 1C integration ----------------

    def td_1c_apply_gtd_first_exchange(self, onec_doc_number, lot_prices):
        self.ensure_one()
        self._td_apply_lot_prices_and_create_svl(
            onec_doc_number=onec_doc_number,
            lot_prices=lot_prices,
            changed=False,
            chatter_message=_("Отримані дані по ГТД з 1С"),
        )

        self._td_sync_book_value_to_lots_from_moves()
        self._td_invalidate_receipt_lot_qty_cache()
        
        return True

    def td_1c_apply_gtd_correction(self, onec_doc_number, lot_prices):
        self.ensure_one()
        self._td_apply_lot_prices_and_create_svl(
            onec_doc_number=onec_doc_number,
            lot_prices=lot_prices,
            changed=True,
            chatter_message=_("Перенесено коригування даних з 1С"),
        )

        self._td_sync_book_value_to_lots_from_moves()
        self._td_invalidate_receipt_lot_qty_cache()

        self._td_sync_book_value_to_lots_from_moves()

        return True
