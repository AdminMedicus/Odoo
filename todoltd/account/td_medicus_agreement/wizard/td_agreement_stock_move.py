from odoo import models, fields, api


class TdStockMove(models.TransientModel):
    _name = "td.agreement.stock.move"
    _description = "ToDo Wizard Stock Move"

    is_selected = fields.Boolean()

    move_id = fields.Many2one(
        comodel_name='stock.move',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
    )
    lot_ids = fields.Many2many(
        comodel_name='stock.lot'
    )
    sale_line_id = fields.Many2one(
        comodel_name='sale.order.line'
    )
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
    )
    quantity = fields.Float()
    product_uom = fields.Many2one(
        comodel_name='uom.uom',
    )
    stock_picking_id = fields.Many2one(
        comodel_name='stock.picking',
    )
    origin_stock_picking_id = fields.Many2one(
        comodel_name='stock.picking',
    )
    price_unit = fields.Float()
    price_subtotal = fields.Float(
        compute='_compute_quantity',
    )

    def _fifo_pick_move_lines(self, move, needed_qty, needed_uom):
        """
        FIFO-отбор строк move.move_line_ids под нужное количество.
        Возвращает: [(move_line, take_qty), ...]
        """
        # Сортируем максимально «по FIFO»: по дате удаления/сроку/создания, затем по id
        lines = move.move_line_ids.sorted(
            key=lambda l: (
                    l.lot_id.removal_date or
                    l.lot_id.life_date or
                    l.lot_id.create_date or
                    l.create_date or
                    l.id
            )
        )

        # Приводим требуемое количество к UoM строк (или move/product), чтобы сравнивать корректно
        # Если нужно работать строго в UoM продукта движения:
        move_uom = move.product_uom or (move.product_id and move.product_id.uom_id)
        if needed_uom and move_uom and needed_uom != move_uom:
            remaining = needed_uom._compute_quantity(needed_qty, move_uom, rounding_method='HALF-UP')
        else:
            remaining = needed_qty

        picked = []
        for ml in lines:
            # Количество в строке (берём qty_done если уже выполнено, иначе зарезервированное product_uom_qty)
            line_qty = ml.qty_done if ml.qty_done else ml.quantity

            # Приведение единиц измерения строки к UoM move для корректного сравнения
            ml_uom = ml.product_uom_id or move_uom
            if ml_uom and move_uom and ml_uom != move_uom:
                avail = ml_uom._compute_quantity(line_qty, move_uom, rounding_method='HALF-UP')
            else:
                avail = line_qty

            if avail <= 0:
                continue

            take = min(avail, remaining)
            if take > 0:
                picked.append((ml, take))
                remaining -= take

            if remaining <= 0:
                break

        return picked

    def action_process_selected(self):
        for rec in self:
            record = {
                'picking_id': rec.origin_stock_picking_id.id,
                'product_id': rec.product_id.id,
                'quantity': rec.quantity,
                'td_quantity': rec.quantity,
                'td_lot_ids': [(6, 0, rec.lot_ids.ids)],
                'sale_line_id': rec.sale_line_id.id,
                'sale_order_id': rec.sale_order_id.id,
                'product_uom': rec.product_uom.id,
                'name': rec.product_id.name,
                'td_price_unit': rec.price_unit,
                'td_price_subtotal': rec.price_subtotal,
            }
            lots = self._fifo_pick_move_lines(rec.move_id, rec.quantity, rec.product_uom)
            record['quantity'] = rec.quantity
            odoo_record = self.env['stock.move'].sudo().create(record)

            for odoo_id, odoo_rec in enumerate(odoo_record.move_line_ids):
                odoo_rec.quant_id = lots[odoo_id][0].quant_id.id
                odoo_rec.lot_id = lots[odoo_id][0].lot_id.id

            odoo_record.quantity = rec.quantity
        self.origin_stock_picking_id.action_confirm()

    @api.onchange('quantity')
    def _compute_quantity(self):
        for rec in self:
            rec.price_subtotal = rec.price_unit * rec.quantity
