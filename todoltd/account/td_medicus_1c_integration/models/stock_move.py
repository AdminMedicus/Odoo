from odoo import fields, models, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    td_currency_rate = fields.Float(
        string="Currency Rate",
        digits=(12, 6),
    )
    td_customs_rate = fields.Float()

    td_customs_value_good = fields.Float(
        compute='_compute_td_customs_value_good',
        store=True
    )
    td_taxes_ids = fields.Many2many(
        comodel_name='account.tax',
        compute='_compute_td_taxes_ids',
        store=True,
        string='Taxes',
    )
    td_taxes = fields.Float(
        compute='_compute_td_taxes',
        store=True,
    )
    td_taxes_price = fields.Float(
        compute='_compute_td_taxes_price',
        store=True
    )
    td_book_value = fields.Float()
    td_price_total = fields.Float(
        compute='_compute_td_price_total',
        store=True
    )

    td_lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        compute='_compute_td_lot_ids'
    )


    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        if any('td_book_value' in vals for vals in vals_list):
            moves._td_sync_td_book_value_to_lots()
        return moves

    def write(self, vals):
        res = super().write(vals)
        if {
            'td_book_value',
            'td_price_unit',
            'td_untaxed_price_unit',
            'move_line_ids',
            'quantity',
        } & set(vals):
            self._td_sync_td_book_value_to_lots()
        return res

    def _td_get_lot_cost_for_sync(self):
        self.ensure_one()

        if self.td_book_value:
            return self.td_book_value

        picking = self.picking_id
        if not picking or picking.picking_type_code != 'incoming':
            return None

        if picking.td_is_import:
            return None

        if 'td_untaxed_price_unit' in self._fields and self.td_untaxed_price_unit:
            return self.td_untaxed_price_unit

        if 'td_price_unit' in self._fields and self.td_price_unit:
            return self.td_price_unit

        purchase_line = self.purchase_line_id
        if purchase_line:
            if (
                    'td_untaxed_price_unit' in purchase_line._fields
                    and purchase_line.td_untaxed_price_unit
            ):
                return purchase_line.td_untaxed_price_unit

            if purchase_line.price_unit:
                return purchase_line.price_unit

        if self.product_id and self.product_id.standard_price:
            return self.product_id.standard_price

        return None

    def _td_get_lots_for_cost_sync(self):
        self.ensure_one()
        lots = self.env['stock.lot']

        for move_line in self.move_line_ids.filtered(lambda line: line.lot_id):
            qty = self._td_get_move_line_done_qty(move_line)
            if qty:
                lots |= move_line.lot_id

        if 'lot_ids' in self._fields:
            lots |= self.lot_ids

        if 'td_lot_ids' in self._fields:
            lots |= self.td_lot_ids

        return lots.filtered(lambda lot: lot.product_id.id == self.product_id.id)

    def _td_write_lot_cost(self, lot, cost):
        vals = {}

        if 'standart_price' in lot._fields:
            vals['standart_price'] = cost
        elif 'standard_price' in lot._fields:
            vals['standard_price'] = cost

        if vals:
            lot.sudo().write(vals)

    def _td_get_move_line_done_qty(self, move_line):
        if 'qty_done' in move_line._fields:
            return move_line.qty_done or 0.0
        return move_line.quantity or 0.0

    def _td_sync_td_book_value_to_lots(self):
        for move in self:
            picking = move.picking_id

            if (
                not picking
                or picking.state != 'done'
                or picking.picking_type_code != 'incoming'
                or not move.product_id
            ):
                continue

            cost = move._td_get_lot_cost_for_sync()
            if cost is None:
                continue

            for lot in move._td_get_lots_for_cost_sync():
                move._td_write_lot_cost(lot, cost)

    @api.depends('lot_ids', 'move_line_ids', 'move_line_ids.quant_id')
    def _compute_td_lot_ids(self):
        for rec in self:
            lots = []
            for move_line in rec.move_line_ids:
                if move_line.quant_id and move_line.quant_id.lot_id:
                    lots.append(move_line.quant_id.lot_id.id)
                elif move_line.lot_id:
                    lots.append(move_line.lot_id.id)
            rec.td_lot_ids = [(6, 0, lots)]

    @api.depends(
        'purchase_line_id.taxes_id',
        'sale_line_id.tax_id',
        'product_id.taxes_id',
        'product_id.supplier_taxes_id',
        'picking_id.picking_type_code',
        'company_id',
    )
    def _compute_td_taxes_ids(self):
        for move in self:
            taxes = move._td_get_taxes()
            move.td_taxes_ids = [(6, 0, taxes.ids)]

    @api.depends('td_taxes_ids', 'td_taxes_ids.amount', 'td_taxes_ids.amount_type')
    def _compute_td_taxes(self):
        for move in self:
            percent_taxes = move.td_taxes_ids.filtered(lambda tax: tax.amount_type == 'percent')
            move.td_taxes = sum(percent_taxes.mapped('amount')) / 100 if percent_taxes else 0.0

    def _td_get_taxes(self):
        self.ensure_one()
        taxes = self.env['account.tax']

        if self.purchase_line_id:
            taxes = self.purchase_line_id.taxes_id
        elif self.sale_line_id:
            taxes = self.sale_line_id.tax_id
        elif self.picking_id and self.picking_id.picking_type_code == 'incoming':
            taxes = self.product_id.supplier_taxes_id
        else:
            taxes = self.product_id.taxes_id

        company = self.company_id
        if company:
            taxes = taxes.filtered(lambda tax: not tax.company_id or tax.company_id == company)

        return taxes

    def _td_get_effective_currency_rate(self):
        self.ensure_one()
        return self.td_currency_rate or (self.picking_id and self.picking_id.td_currency_rate) or 1.0

    def _td_get_tax_partner(self):
        self.ensure_one()
        if self.purchase_line_id and self.purchase_line_id.order_id:
            return self.purchase_line_id.order_id.partner_id
        if self.sale_line_id and self.sale_line_id.order_id:
            return self.sale_line_id.order_id.partner_id
        if self.picking_id:
            return self.picking_id.partner_id
        return False

    def _td_get_tax_computation(self):
        self.ensure_one()
        taxes = self._td_get_taxes()
        quantity = self.quantity or 0.0
        unit_price = self.td_price_unit or 0.0

        if not quantity:
            return {
                'total_excluded': 0.0,
                'total_included': 0.0,
            }

        if not taxes:
            total = unit_price * quantity
            return {
                'total_excluded': total,
                'total_included': total,
            }

        return taxes.compute_all(
            unit_price,
            quantity=quantity,
            product=self.product_id,
            partner=self._td_get_tax_partner(),
        )

    def _td_get_origin_amount_total(self):
        self.ensure_one()
        taxes_data = self._td_get_tax_computation()
        return taxes_data.get('total_included', 0.0)

    def _td_get_origin_amount_untaxed_total(self):
        self.ensure_one()
        taxes_data = self._td_get_tax_computation()
        return taxes_data.get('total_excluded', 0.0)

    def _td_get_origin_tax_amount_total(self):
        self.ensure_one()
        taxes_data = self._td_get_tax_computation()
        return taxes_data.get('total_included', 0.0) - taxes_data.get('total_excluded', 0.0)

    def _td_get_company_amount_total(self):
        self.ensure_one()
        return self._td_get_origin_amount_total() * self._td_get_effective_currency_rate()

    def _td_get_company_amount_untaxed_total(self):
        self.ensure_one()
        return self._td_get_origin_amount_untaxed_total() * self._td_get_effective_currency_rate()

    @api.depends(
        'td_taxes',
        'td_taxes_ids',
        'td_taxes_ids.amount',
        'td_taxes_ids.amount_type',
        'quantity',
        'td_price_unit',
        'td_untaxed_price_unit',
        'picking_id.td_is_import',
        'td_currency_rate',
        'picking_id.td_currency_rate',
        'purchase_line_id.taxes_id',
        'sale_line_id.tax_id',
    )
    def _compute_td_taxes_price(self):
        for move in self:
            tax_amount = move._td_get_origin_tax_amount_total()
            if move.picking_id.td_is_import:
                move.td_taxes_price = tax_amount * move._td_get_effective_currency_rate()
            else:
                move.td_taxes_price = tax_amount

    @api.depends(
        'td_taxes_price',
        'td_book_value',
        'td_customs_value_good',
        'td_currency_rate',
        'quantity',
        'td_price_unit',
        'td_untaxed_price_unit',
        'picking_id.td_is_import',
        'purchase_line_id.taxes_id',
        'sale_line_id.tax_id',
    )
    def _compute_td_price_total(self):
        for move in self:
            if move.picking_id.td_is_import:
                move.td_price_total = move._td_get_company_amount_untaxed_total() + move.td_taxes_price
            else:
                if move.bom_line_id:
                    move.td_price_total = move.td_price_subtotal + move.td_taxes_price
                else:
                    move.td_price_total = move._td_get_origin_amount_untaxed_total() + move.td_taxes_price

    @api.depends('td_currency_rate', 'td_price_unit', 'product_id', 'picking_id.td_currency_rate')
    def _compute_td_customs_value_good(self):
        for move in self:
            rate = move._td_get_effective_currency_rate()

            if move.product_id and move.td_price_unit:
                move.td_customs_value_good = move.td_price_unit * rate
            else:
                move.td_customs_value_good = 0.0
