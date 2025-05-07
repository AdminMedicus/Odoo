from odoo import _, api, fields, models, SUPERUSER_ID


class Agreement(models.Model):
    _inherit = "td.agreement"

    closing_reason_id = fields.Many2one(
        comodel_name="td.agreement.closing.reason",
        string="Closing Reason",
    )
    is_closed = fields.Boolean(string="Closed", tracking=True)
    discount = fields.Float(
        string="Discount (%)",
        default=0.0
    )

    sale_order_ids = fields.One2many(
        comodel_name='sale.order',
        inverse_name='td_agreement_id',
        string="Sale Order"
    )

    td_sale_order_count = fields.Integer(
        string='Sale Order Count',
        compute='_compute_sale_order_count'
    )

    purchase_order_ids = fields.One2many(
        comodel_name='purchase.order',
        inverse_name='td_agreement_id',
        string="Purchase Order"
    )

    td_purchase_order_count = fields.Integer(
        string='Purchase Order Count',
        compute='_compute_purchase_order_count'
    )

    account_move_ids = fields.One2many(
        comodel_name='account.move',
        inverse_name='td_agreement_id',
        string="Account Move"
    )

    td_account_move_count = fields.Float(
        string='Account Move Count',
        compute='_compute_account_move_count'
    )
    td_account_bill_count = fields.Integer(
        string='Account Move Bills Count',
        compute='_compute_account_bill_count'
    )
    td_timeline_percentage = fields.Char(
        string='Timeliness of Payment (%)',
        compute='_compute_timeline_percentage'
    )

    @api.onchange('account_move_ids')
    def _compute_timeline_percentage(self):
        invoices = self.env['account.move'].search([('td_agreement_id', '=', self.id), ('move_type', '=', 'out_invoice')])
        total_invoices = 0
        on_time_invoices = 0
        for invoice in invoices:
            if invoice.status_in_payment == 'paid':
                total_invoices += 1
                payment = invoice.invoice_payments_widget
                try:
                    payment_date = payment['content'][0]['date']
                    if payment_date and payment_date <= invoice.invoice_date_due:
                        on_time_invoices += 1
                except:
                    pass

        if total_invoices > 0:
            timeliness_percentage_nf = (on_time_invoices / total_invoices) * 100
            timeliness_percentage = round(timeliness_percentage_nf, 2)
        else:
            timeliness_percentage = 0

        self.td_timeline_percentage = str(timeliness_percentage) + '%'

    @api.onchange('account_move_ids')
    def _compute_account_bill_count(self):
        sudo_self = self.with_user(SUPERUSER_ID)
        domain = [
            ('td_agreement_id', '=', self.id),
            ('move_type', 'in', ['in_invoice', 'in_refund'])
        ]
        for agreement in sudo_self:
            agreement.td_account_bill_count = len(self.env['account.move'].search(domain=domain))

    def _compute_supplier_invoice_count(self):
        # retrieve all children partners and prefetch 'parent_id' on them
        all_partners = self.with_context(active_test=False).search_fetch(
            [('id', 'child_of', self.ids)],
            ['parent_id'],
        )
        supplier_invoice_groups = self.env['account.move']._read_group(
            domain=[('partner_id', 'in', all_partners.ids),
                    *self.env['account.move']._check_company_domain(self.env.company),
                    ('move_type', 'in', ('in_invoice', 'in_refund'))],
            groupby=['partner_id'], aggregates=['__count']
        )
        self_ids = set(self._ids)

        self.supplier_invoice_count = 0
        for partner, count in supplier_invoice_groups:
            while partner:
                if partner.id in self_ids:
                    partner.supplier_invoice_count += count
                partner = partner.parent_id

    @api.onchange('account_move_ids')
    def _compute_account_move_count(self):
        sudo_self = self.with_user(SUPERUSER_ID)
        self.td_account_move_count = 0.0
        for agreement in sudo_self:
            for account_move in agreement.account_move_ids:
                if account_move.move_type == 'out_invoice' and account_move.state == 'posted':
                    agreement.td_account_move_count += account_move.amount_total_in_currency_signed

    @api.onchange('purchase_order_ids')
    def _compute_purchase_order_count(self):
        sudo_self = self.with_user(SUPERUSER_ID)
        for agreement in sudo_self:
            agreement.td_purchase_order_count = len(agreement.purchase_order_ids)

    @api.onchange('sale_order_ids')
    def _compute_sale_order_count(self):
        sudo_self = self.with_user(SUPERUSER_ID)
        for agreement in sudo_self:
            agreement.td_sale_order_count = len(agreement.sale_order_ids)

    def action_mark_closed(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reason for closing'),
            'res_model': 'td.agreement.closing.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('td_yaroslav_agreement.td_agreement_closing_wizard_form_view').id,
            'target': 'new',
            'context': {'default_agreement_id': self.id},
        }

    def action_restore_agreement(self):
        self.ensure_one()
        self.write({
            'is_closed': False,
            'closing_reason_id': False,
        })


    def action_view_sale_order(self):
        action = self.env.ref('sale.action_orders').sudo().read()[0]
        action['domain'] = [
            ('td_agreement_id', '=', self.id),
        ]
        return action

    def action_view_purchase_order(self):
        action = self.env.ref('purchase.purchase_form_action').sudo().read()[0]
        action['domain'] = [
            ('td_agreement_id', '=', self.id),
        ]
        return action

    def action_view_account_move(self):
        action = self.env.ref('account.action_move_journal_line').sudo().read()[0]
        action['domain'] = [
            ('td_agreement_id', '=', self.id),
            ('move_type', '=', 'out_invoice')
        ]
        action['context'] = ''
        return action

    def action_view_account_bill(self):
        action = self.env.ref('account.action_move_journal_line').sudo().read()[0]
        action['domain'] = [
            ('td_agreement_id', '=', self.id),
            ('move_type', 'in', ['in_invoice', 'in_refund'])
        ]
        action['context'] = ''
        return action

    def action_open_partner_ledger(self):
        action = self.env.ref("account_reports.action_account_report_partner_ledger").sudo().read()[0]
        partner_id = self.partner_id.id
        action['params'] = {
            'options': {
                'partner_ids': [partner_id],
                'td_agreement_id': self.id,
                'td_custom_groupby': 'agreement',
                'unfolded_lines': [f'~account.report~14|~res.partner~{partner_id}']},
            'ignore_session': True,
        }
        return action

    def plug_button(self):
        # Method that makes a button inactive
        pass
