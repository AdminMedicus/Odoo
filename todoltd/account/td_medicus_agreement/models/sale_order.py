from odoo import models, fields, api


class SaleOrder(models.Model):
    _description = "Sale Order"
    _inherit = "sale.order"

    implementation_document = fields.Selection(
        selection=[
            ('exp_inv', 'Expenditure invoice'),
            ('act_res_st', 'Act of responsible storage'),
            ('move', 'Movement')
        ]
    )

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

    @api.onchange('implementation_document')
    def _onchange_implementation_document(self):
        for order in self:
            if order.partner_id:
                if order.implementation_document == 'exp_inv':
                    order.td_agreement_id = (
                        order.partner_id.standard_agreement_expense_id.id
                    )
                elif order.implementation_document == 'act_res_st':
                    order.td_agreement_id = (
                        order.partner_id.standard_agreement_custody_id.id
                    )

    def action_confirm(self):
        action = super().action_confirm()
        for res in self:
            if res.picking_ids:
                for picking in res.picking_ids:
                    picking.implementation_document = (
                        res.implementation_document
                    )
        return action
