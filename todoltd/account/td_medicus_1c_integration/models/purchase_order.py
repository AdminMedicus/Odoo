from odoo import fields, models, api, SUPERUSER_ID


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    td_type_of_trade = fields.Selection(
        [
            ('prepayment', 'Prepayment'),
            ('credit', 'Credit'),
            ('res_storage', 'Responsible Storage'),
        ], default='prepayment'
    )

    td_is_import = fields.Boolean(
        string="Import",
        default=False,
        compute='_compute_td_is_import',
        store=True
    )

    @api.onchange('td_type_of_trade')
    def _onchange_td_type_of_trade(self):
        for order in self:
            if order.td_type_of_trade and order.td_type_of_trade in ['prepayment', 'credit']:
                rec = self.env['stock.picking.type'].search([
                    ('td_type_of_trade', '=', 'prepayment_credit')], limit=1)
                if rec:
                    order.picking_type_id = rec.id
            elif order.td_type_of_trade and order.td_type_of_trade == 'res_storage':
                rec = self.env['stock.picking.type'].search([
                    ('td_type_of_trade', '=', 'res_storage')], limit=1)
                if rec:
                    order.picking_type_id = rec.id

    @api.depends('currency_id')
    def _compute_td_is_import(self):
        for order in self:
            company_currency = order.company_id.currency_id
            if order.currency_id and order.currency_id != company_currency:
                order.td_is_import = True
            else:
                order.td_is_import = False

    def _create_picking(self):
        res = super()._create_picking()

        for picking in self.picking_ids:
            if picking.picking_type_code == 'incoming':
                if 'IMPORT' not in picking.name and self.td_is_import:
                    picking.name = picking.name.replace('ОС/IN/', 'ОС/IN/IMPORT/')

            picking.td_currency_id = self.currency_id.id
            picking.td_type_of_trade = self.td_type_of_trade
            picking.td_is_import = self.td_is_import
            if 'td_agreement_id' in picking._fields:
                picking.td_agreement_id = self.td_agreement_id.id if self.td_agreement_id else False
        return res
