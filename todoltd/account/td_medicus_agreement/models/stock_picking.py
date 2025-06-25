from datetime import date
from email.policy import default

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    implementation_document = fields.Selection(
        selection=[
            ('exp_inv', 'Expenditure invoice'),
            ('act_res_st', 'Act of responsible storage'),
            ('move', 'Movement')
        ],
    )
    td_is_change = fields.Boolean(
        default=True
    )
    td_sale_id_name = fields.Char(
        related='sale_id.name'
    )
    date_agreement_start = fields.Date(
        default=lambda self: date.today() - relativedelta(months=6),
    )
    date_agreement_end = fields.Date(
        default=lambda self: date.today(),
    )
    sale_order_ids = fields.Many2many(
        comodel_name='sale.order',
        compute='_compute_sale_order_ids'
    )
    sale_order_count = fields.Integer(
        compute='_compute_sale_order_ids'
    )
    td_total_amount = fields.Float(
        compute='_compute_td_total_amount'
    )

    @api.onchange('move_ids_without_package')
    def _compute_td_total_amount(self):
        for rec in self:
            rec.td_total_amount = sum([
                move.td_price_subtotal
                for move in rec.move_ids_without_package
            ])

    def button_validate(self):
        res = super().button_validate()
        picking_ids = self.move_ids.move_dest_ids.picking_id
        for picking in picking_ids:
            picking.implementation_document = self.implementation_document
        return res

    def create_implementation_document_sale_order(self):
        self.ensure_one()
        pricelist = set(
            rec.pricelist_id.id
            for rec in self.sale_order_ids
            if rec and rec.pricelist_id
        )
        if len(pricelist) > 1:
            pricelist_id = False
        elif len(pricelist) == 0:
            pricelist_id = False
        else:
            pricelist_id = list(pricelist)[0]

        if len(self.move_ids_without_package) == 0:
            raise ValidationError(_(
                "Products not selected and their quantity"
            ))

        sale_order = self.env['sale.order'].sudo().create({
            'partner_id': self.partner_id.id,
            'sub_client_id': self.sub_client_id.id
            if self.sub_client_id else False,
            'pricelist_id': pricelist_id,
            'implementation_document': 'exp_inv',
            'td_agreement_id': self.partner_id.standard_agreement_expense_id.id
            if self.partner_id.standard_agreement_expense_id else False
        })
        self.env['sale.order.line'].sudo().create([
            {
                'order_id': sale_order.id,
                'product_id': rec.product_id.id,
                'product_template_id': rec.product_id.product_tmpl_id.id
                if rec.product_id.product_tmpl_id else False,
                'product_uom_qty': rec.quantity,
                'product_uom': rec.product_uom.id
                if rec.product_uom else False,
                'price_unit': self.product_price_unit(rec),
            } for rec in self.move_ids_without_package
        ])

        self.sale_id = sale_order.id
        self.origin = sale_order.name
        self.td_is_change = False

        return {
            'name': _('Sale Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'res_id': sale_order.id
        }

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            'name': _('Sale Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'current',
            'res_id': self.sale_id.id
        }

    def product_price_unit(self, record):
        if record.sale_order_id:
            order_line = self.env['sale.order.line'].sudo().search([
                ('order_id', '=', record.sale_order_id.id),
                ('product_id', '=', record.product_id.id),
            ], limit=1)
            if order_line:
                return order_line.price_unit
        return False

    def action_see_sale_orders(self):
        return {
            'name': _('Sale Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('id', 'in', self.sale_order_ids.ids)],
        }

    @api.depends('move_ids_without_package')
    def _compute_sale_order_ids(self):
        for rec in self:
            sale_orders = set()
            for move in rec.move_ids_without_package:
                sale_orders.add(move.sale_order_id.id)
            rec.sale_order_ids = [(6, 0, sale_orders)]
            rec.sale_order_count = len(sale_orders)

    def action_show_product_list(self):
        self.ensure_one()
        if not self.implementation_document:
            raise ValidationError(_(
                "You need to specify the implementation document"
            ))
        if not self.date_agreement_start:
            raise ValidationError(_(
                "You need to specify the start date of the agreement"
            ))
        if not self.date_agreement_end:
            raise ValidationError(_(
                "You need to specify the end date of the agreement"
            ))

        if self.sub_client_id:
            sale_orders = self.env['sale.order'].search([
                ('partner_id', '=', self.partner_id.id),
                ('sub_client_id', '=', self.sub_client_id.id)
            ])
            if sale_orders:
                records = self.search([
                    "&", "&", "&", "&",
                    ('sale_id', 'in', sale_orders.ids),
                    ('picking_type_id.code', '=', 'outgoing'),
                    ("implementation_document", "=",
                     self.implementation_document),
                    ("scheduled_date", ">=", self.date_agreement_start),
                    ("scheduled_date", "<=", self.date_agreement_end)
                ])
            else:
                records = self.browse([])
        else:
            records = self.search([
                "&", "&", "&", "&", "&",
                ('sub_client_id', '=', False),
                ('partner_id', '=', self.partner_id.id),
                ('picking_type_id.code', '=', 'outgoing'),
                ("implementation_document", "=", self.implementation_document),
                ("scheduled_date", ">=", self.date_agreement_start),
                ("scheduled_date", "<=", self.date_agreement_end)
            ])

        stock_move_records = records.move_ids_without_package

        td_stock_move_records = self.env[
            'td.agreement.stock.move'
        ].sudo().create([
            {
                'move_id': move_id.id,
                'product_id': move_id.product_id.id,
                'lot_ids': move_id.lot_ids.ids,
                'sale_order_id': move_id.sale_order_id.id,
                'sale_line_id': move_id.sale_line_id.id,
                'quantity': move_id.quantity,
                'product_uom': move_id.product_uom.id,
                'stock_picking_id': move_id.picking_id.id,
                'origin_stock_picking_id': self.id,
                'price_unit': move_id.sale_line_id.price_unit
                if move_id.sale_line_id else 0,
                'price_subtotal': move_id.sale_line_id.price_subtotal
                if move_id.sale_line_id else 0,
                } for move_id in stock_move_records
        ])

        return {
            'name': _('Select Record'),
            'type': 'ir.actions.act_window',
            'res_model': 'td.agreement.stock.move',
            'view_mode': 'list',
            'target': 'new',
            'domain': [('id', 'in', td_stock_move_records.ids)],
        }
