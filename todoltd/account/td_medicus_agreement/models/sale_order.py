from odoo import models, api


class SaleOrder(models.Model):
    _description = "Sale Order"
    _inherit = "sale.order"

    @api.depends('partner_id', 'company_id', 'td_agreement_id')
    def _compute_pricelist_id(self):
        for order in self:
            if order.td_agreement_id and order.td_agreement_id.pricelist_id:
                order.pricelist_id = order.td_agreement_id.pricelist_id.id
                continue
            if order.state != 'draft':
                continue
            if not order.partner_id:
                order.pricelist_id = False
                continue
            order = order.with_company(order.company_id)
            order.pricelist_id = order.partner_id.property_product_pricelist

    @api.onchange('partner_id')
    def _compute_td_agreement_id(self):
        for order in self:
            if order.partner_id:
                main_contract = self.env['td.agreement'].search([
                    ('partner_id', '=', order.partner_id.id),
                    ('main_contract', '=', True)
                ], limit=1)
                if main_contract:
                    order.td_agreement_id = main_contract.id
