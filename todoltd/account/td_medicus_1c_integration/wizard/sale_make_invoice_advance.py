from odoo import fields, models, Command, api, _
from odoo.exceptions import UserError, ValidationError


class SaleMakeInvoiceAdvance(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    td_advance_payment_method = fields.Selection(
        selection=[
            ('delivered', "Regular invoice"),
            ('percentage', "Down payment (percentage)"),
            ('fixed', "Down payment (fixed amount)"),
        ],
        string="Create Invoice",
        default='delivered',
    )
    td_advance_payment_method_one = fields.Selection(
        selection=[
            ('percentage', "Down payment (percentage)"),
            ('fixed', "Down payment (fixed amount)"),
        ],
        string="Create Invoice",
        default='fixed',
    )
    td_choose_payment_method = fields.Boolean(
        compute='_compute_td_choose_payment_method'
    )
    advance_payment_method = fields.Selection(
        compute='_compute_advance_payment_method',
        default='fixed'
    )

    amount = fields.Float(
        default=100
    )

    @api.depends('sale_order_ids')
    def _compute_td_choose_payment_method(self):
        for line in self:
            if line.sale_order_ids:
                outgoing = line.sale_order_ids.picking_ids.filtered(
                    lambda pick: pick.picking_type_code == 'outgoing'
                )
                if outgoing:
                    done = outgoing.filtered(
                        lambda pick: pick.state == 'done'
                    )
                    if len(done) == len(outgoing):
                        line.td_choose_payment_method = True
                    else:
                        line.td_choose_payment_method = False
                else:
                    line.td_choose_payment_method = False
            else:
                line.td_choose_payment_method = False

    @api.depends('td_advance_payment_method', 'td_advance_payment_method_one', 'td_choose_payment_method')
    def _compute_advance_payment_method(self):
        for line in self:
            if line.td_choose_payment_method:
                if line.td_advance_payment_method:
                    line.advance_payment_method = (
                        line.td_advance_payment_method
                    )
                else:
                    line.advance_payment_method = 'delivered'
            else:
                if line.td_advance_payment_method_one:
                    line.advance_payment_method = (
                        line.td_advance_payment_method_one
                    )
                else:
                    line.advance_payment_method = 'fixed'

    def create_invoices(self):
        self._check_amount_is_positive()
        invoices = self._create_invoices(self.sale_order_ids)
        sale_order = self.env.context.get("active_id")
        if sale_order:
            for invoice in invoices:
                invoice.td_order_id = sale_order
                if invoice.td_advance_payment_method == 'delivered':
                    invoice.td_prepayment = False
        return self.sale_order_ids.action_view_invoice(invoices=invoices)

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
        if self.advance_payment_method == 'percentage':
            percent = self.amount
            if not (0 < percent <= 100):
                raise ValidationError(
                    _("Percentage (amount) must be between 0 and 100.")
                )

            invoice_line_data = []
            for line in order.order_line.filtered(
                    lambda ord_l: not ord_l.display_type and ord_l.product_id):
                if line.qty_to_invoice <= 0:
                    continue

                price_with_percent = line.price_unit * (percent / 100.0)

                invoice_line_data.append({
                    'origin_line': line,
                    'values': {
                        'name': _(
                            'Down payment invoice %s'
                        ) % line.product_id.name,
                        'product_id': line.product_id.id,
                        'display_type': False,
                        'product_uom_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        # 'price_unit': line.price_unit,
                        'price_unit': price_with_percent,
                        'tax_id': [(6, 0, line.tax_id.ids)],
                        'order_id': line.order_id.id,
                        'is_downpayment': True,
                        'sequence': 99
                    }
                })

        elif self.advance_payment_method == 'fixed':
            fixed_amount = self.fixed_amount
            if fixed_amount <= 0:
                raise ValidationError(_("Fixed amount must be positive."))

            order_total = sum(line.price_unit * line.product_uom_qty for line in order.order_line.filtered(
                lambda l: not l.display_type and l.product_id and l.qty_to_invoice > 0))
            if order_total <= 0:
                raise UserError(_("The sales order has no invoiceable lines with positive total."))

            invoice_line_data = []
            for line in order.order_line.filtered(
                    lambda l: not l.display_type and l.product_id and l.qty_to_invoice > 0):
                line_total = line.price_unit * line.product_uom_qty
                line_share = line_total / order_total
                line_amount = fixed_amount * line_share

                price_unit = line_amount / line.product_uom_qty if line.product_uom_qty else 0

                invoice_line_data.append({
                    'origin_line': line,
                    'values': {
                        'name': _('Down payment invoice %s') % line.product_id.name,
                        'product_id': line.product_id.id,
                        'display_type': False,
                        'product_uom_qty': line.product_uom_qty,
                        'product_uom': line.product_uom.id,
                        'price_unit': price_unit,
                        'tax_id': [(6, 0, line.tax_id.ids)],
                        'order_id': line.order_id.id,
                        'is_downpayment': True,
                        'sequence': 99
                    }
                })

        if not invoice_line_data:
            raise UserError(
                _("No invoiceable lines found in the sales order.")
            )

        SaleOrderline = self.env['sale.order.line'].with_context(
            sale_no_log_for_new_lines=True)
        if not any(line.display_type and line.is_downpayment
                   for line in order.order_line):
            SaleOrderline.create(
                self._prepare_down_payment_section_values(order)
            )

        downpayment_so_lines = []
        for entry in invoice_line_data:
            new_line = SaleOrderline.create(entry['values'])
            downpayment_so_lines.append((new_line, entry['origin_line']))

        invoice_vals = {
            **order._prepare_invoice(),
            'td_prepayment': True,
            'td_advance_payment_method': self.advance_payment_method,
            'invoice_line_ids': [
                Command.create({
                    **new_line._prepare_invoice_line(
                        quantity=new_line.product_uom_qty),
                    'td_order_line_id': origin_line.id,
                    'tax_ids': [(6, 0, origin_line.tax_id.ids)],

                }) for new_line, origin_line in downpayment_so_lines],
        }
        invoice = self.env['account.move'].sudo().create(invoice_vals)

        poster = (
            self.env.user.id
            if self.env.user._is_internal()
            else self.env.ref('base.user_root').id
        )
        invoice.with_user(poster).message_post_with_source(
            'mail.message_origin_link',
            render_values={'self': invoice, 'origin': order},
            subtype_xmlid='mail.mt_note',
        )
        order.with_user(poster).message_post(
            body=_("%s has been created",
                   invoice._get_html_link(title=_("Down payment invoice"))),
        )

        return invoice
