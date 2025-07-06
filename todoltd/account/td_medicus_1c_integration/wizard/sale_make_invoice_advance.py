from odoo import fields, models, Command, api, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError


class SaleMakeInvoiceAdvance(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    td_advance_payment_method = fields.Selection(
        selection=[
            ('delivered', "Regular invoice"),
            ('percentage', "Down payment (percentage)"),
        ],
        string="Create Invoice",
        default='delivered',
        required=True,
    )
    advance_payment_method = fields.Selection(
        compute='_compute_advance_payment_method'
    )

    amount = fields.Float(
        default=100
    )

    @api.depends('td_advance_payment_method')
    def _compute_advance_payment_method(self):
        for line in self:
            if line.td_advance_payment_method:
                line.advance_payment_method = line.td_advance_payment_method
            else:
                line.advance_payment_method = 'delivered'

    def create_invoices(self):
        self._check_amount_is_positive()
        invoices = self._create_invoices(self.sale_order_ids)
        sale_order = self.env.context.get("active_id")
        if sale_order:
            for invoice in invoices:
                invoice.td_order_id = sale_order
        return self.sale_order_ids.action_view_invoice(invoices=invoices)

    # def _create_invoices(self, sale_orders):
    #     self.ensure_one()

        # if self.advance_payment_method == 'delivered':
        #     return sale_orders._create_invoices(
        #         final=self.deduct_down_payments,
        #         grouped=not self.consolidated_billing
        #     )
        #
        # self.sale_order_ids.ensure_one()
        # self = self.with_company(self.company_id)
        # order = self.sale_order_ids
        #
        # percent = self.amount
        # SaleOrderLine = self.env['sale.order.line'].with_context(sale_no_log_for_new_lines=True)
        # invoice_sale_line_vals = []
        #
        # for line in order.order_line.filtered(lambda l: not l.display_type and l.product_id):
        #     if line.qty_to_invoice <= 0:
        #             continue
        #
        #     price_unit = line.price_unit * (percent / 100.0)
        #
        #     invoice_sale_line_vals.append({
        #         'name': line.name,
        #         'product_id': line.product_id.id,
        #         'product_uom_qty': line.product_uom_qty,
        #         'product_uom': line.product_uom.id,
        #         'price_unit': price_unit,
        #         'tax_id': [(6, 0, line.tax_id.ids)],
        #         'order_id': line.order_id.id,
        #     })

    def _create_invoices(self, sale_orders):
        self.ensure_one()

        if self.advance_payment_method == 'delivered':
            return sale_orders._create_invoices(
                final=self.deduct_down_payments,
                grouped=not self.consolidated_billing
            )

        self.sale_order_ids.ensure_one()
        self = self.with_company(self.company_id)
        order = self.sale_order_ids

        percent = self.amount
        if not (0 < percent <= 100):
            raise ValidationError(_("Percentage (amount) must be between 0 and 100."))

        # SaleOrderLine = self.env['sale.order.line'].with_context(sale_no_log_for_new_lines=True)

        # 1) Создаем строки инвойса с % от строк SO
        invoice_line_data = []
        for line in order.order_line.filtered(lambda l: not l.display_type and l.product_id):
            if line.qty_to_invoice <= 0:
                continue

            invoice_line_data.append({
                'origin_line': line,
                'values': {
                    'name': _('Down payment invoice %s') % line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'price_unit': line.price_unit,
                    'tax_id': [(6, 0, line.tax_id.ids)],
                    'order_id': line.order_id.id,
                    'is_downpayment': True,
                }
            })

        if not invoice_line_data:
            raise UserError(_("No invoiceable lines found in the sales order."))

        # 2) Создаем временные SO линии для down payment (будут связаны с инвойсом)

        SaleOrderline = self.env['sale.order.line'].with_context(sale_no_log_for_new_lines=True)
        if not any(line.display_type and line.is_downpayment for line in order.order_line):
            SaleOrderline.create(
                self._prepare_down_payment_section_values(order)
            )

        # values, accounts = self._prepare_down_payment_lines_values(order)
        # down_payment_lines = SaleOrderline.create(values)
        #
        downpayment_so_lines = []
        for entry in invoice_line_data:
            new_line = SaleOrderline.create(entry['values'])
            downpayment_so_lines.append((new_line, entry['origin_line']))

        # 3) Создаем инвойс с этими линиями
        invoice_vals = {
            **order._prepare_invoice(),
            'td_prepayment': True,
            'td_advance_payment_method': 'percentage',
            'invoice_line_ids': [
                Command.create({
                    **new_line._prepare_invoice_line(quantity=new_line.product_uom_qty),
                    'td_order_line_id': origin_line.id,
                    'td_purchase_price': origin_line.purchase_price,
                    'td_margin': origin_line.margin,
                    'td_margin_percent': origin_line.margin_percent,

                }) for new_line, origin_line in downpayment_so_lines],
        }
        invoice = self.env['account.move'].sudo().create(invoice_vals)

        # 4) Создаем в SO линии раздела down payment с ссылкой на инвойс
        #    (например, строки с display_type='line_section' или display_type='line_note' и флагом is_downpayment)
        # downpayment_section_vals = self._prepare_down_payment_section_values(order)
        # downpayment_section = SaleOrderLine.create(downpayment_section_vals)

        # for line in downpayment_so_lines:
        #     line_vals = {
        #         'name': _('Down payment for invoice %s') % invoice.name,
        #         'order_id': order.id,
        #         'product_id': False,
        #         'product_uom_qty': 1,
        #         'price_unit': 0.0,
        #         'display_type': 'line_note',
        #         'is_downpayment': True,
        #         # 'sale_line_ids': [(6, 0, [])],
        #     }
        #     SaleOrderLine.create(line_vals)

        # 5) Публикуем сообщения в chatter
        poster = self.env.user._is_internal() and self.env.user.id or self.env.ref('base.user_root').id
        invoice.with_user(poster).message_post_with_source(
            'mail.message_origin_link',
            render_values={'self': invoice, 'origin': order},
            subtype_xmlid='mail.mt_note',
        )
        order.with_user(poster).message_post(
            body=_("%s has been created", invoice._get_html_link(title=_("Down payment invoice"))),
        )

        return invoice