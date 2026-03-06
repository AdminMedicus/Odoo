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
        # selection_add=[('import', 'Import data to 1C')],
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
        """
        The "Prepared" button for imported receipts:
        - changes the status to state='import' (Awaiting allocation of expenses from the customs declaration)
        - adds to the exchange queue (ata.exchange.queue) so that 1C can retrieve the data
        """

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
        'sale_id', 
        'sale_id.amount_untaxed', 
        'sale_id.amount_tax',
        'td_total_tax',
        'td_total_without_tax',
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
                    rec.td_total_without_tax = sum(lines.mapped('td_customs_value_good')) or 0.0
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

        seq = self._ensure_sequence(
            'td.lot.daily', 'TD daily lot sequence', for_date
        )

        base = seq.with_context(
            ir_sequence_date=for_date
        ).next_by_id(sequence_date=for_date)

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
                if (
                        "unique" in msg
                        or "duplicate" in msg
                        or "already exists" in msg
                ):
                    continue
                raise
        raise UserError(
            _(
                "Failed to generate a unique lot name for item %s "
                "after %s attempts."
            ) % (product.display_name, MAX_ATTEMPTS)
        )

    def _create_lot_ids_for_move(self):
        Lot = self.env['stock.lot']
        today = fields.Date.context_today(self)

        for picking in self:
            company_id = picking.company_id.id if picking.company_id else False

            # --- PARTS (tracking == 'lot') ---
            processed_ml_ids = set()
            for ml in picking.move_line_ids.filtered(
                    lambda lin: lin.product_id
                    and lin.product_id.tracking == 'lot'
            ):
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
                          and sum(m.move_line_ids.mapped("qty_done")) > 0
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

                qty_done = sum(move.move_line_ids.mapped("qty_done"))

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

    def button_validate(self):
        res = super().button_validate()

        if not self.sale_id:
            self._assign_serial_ref()
            self._create_lot_ids_for_move()

        for picking in self:
            for move in picking.move_ids:
                for lot in move.lot_ids:
                    uktzed_line = move.move_line_ids.filtered(lambda lin: lin.lot_id.id == lot.id)
                    move.lot_ids.write({
                        "td_uktzed_code_id": (uktzed_line.td_uktzed_code_id.id if uktzed_line else False)
                    })
                    move.td_uktzed_code_id = (uktzed_line.td_uktzed_code_id.id if uktzed_line else False)

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

            if new_price is None:
                continue

            old_price = getattr(lot, "standart_price", 0.0) or 0.0
            if float(new_price) == float(old_price):
                continue

            # update lot cost
            lot.sudo().write({"standart_price": new_price})

            # qty in internal (company-aware)
            qty = lot._td_get_internal_qty(company=self.company_id)
            if not qty:
                continue

            value_diff = (float(new_price) - float(old_price)) * float(qty)
            if abs(value_diff) < 1e-9:
                continue

            # find related move via move lines
            ml = self.move_line_ids.filtered(lambda l: l.lot_id.id == lot.id and l.product_id.id == lot.product_id.id)[
                :1]
            move = ml.move_id if ml else False

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
        return True

    def td_1c_apply_gtd_correction(self, onec_doc_number, lot_prices):
        self.ensure_one()
        self._td_apply_lot_prices_and_create_svl(
            onec_doc_number=onec_doc_number,
            lot_prices=lot_prices,
            changed=True,
            chatter_message=_("Перенесено коригування даних з 1С"),
        )
        return True

    # def button_validate(self):
    #     # if not self.td_is_import:
    #
    #     res = super().button_validate()
    #
    #     if not self.sale_id:
    #         self._assign_serial_ref()
    #         self._create_lot_ids_for_move()
    #
    #     for picking in self:
    #         for move in picking.move_ids:
    #
    #             for lot in move.lot_ids:
    #                 uktzed_line = move.move_line_ids.filtered(
    #                     lambda lin: lin.lot_id.id == lot.id
    #                 )
    #                 move.lot_ids.write({
    #                     "td_uktzed_code_id": (
    #                         uktzed_line.td_uktzed_code_id.id
    #                         if uktzed_line else False
    #                     )
    #                 })
    #                 move.td_uktzed_code_id = (
    #                     uktzed_line.td_uktzed_code_id.id
    #                     if uktzed_line else False
    #                 )
    #     return res
