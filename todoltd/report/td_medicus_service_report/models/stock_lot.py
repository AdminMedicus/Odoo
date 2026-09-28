# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from .relation_chatter import post_relation_changes, relation_snapshots


class StockLot(models.Model):
    _inherit = 'stock.lot'

    td_agreement_ids = fields.Many2many(
        comodel_name='td.agreement',
        relation='td_agreement_stock_lot_rel',
        column1='lot_id',
        column2='agreement_id',
        string='Agreements',
    )
    td_agreement_count = fields.Integer(
        string='Agreements Count',
        compute='_compute_td_agreement_count',
    )

    @api.depends('td_agreement_ids')
    def _compute_td_agreement_count(self):
        for lot in self:
            lot.td_agreement_count = len(lot.td_agreement_ids)

    @api.model_create_multi
    def create(self, vals_list):
        lots = super().create(vals_list)
        post_relation_changes(lots, 'td_agreement_ids',
                              inverse_field_name='td_lot_ids')
        return lots

    def write(self, vals):
        previous = (relation_snapshots(self, 'td_agreement_ids')
                    if 'td_agreement_ids' in vals else None)
        result = super().write(vals)
        if previous is not None:
            post_relation_changes(self, 'td_agreement_ids', previous,
                                  inverse_field_name='td_lot_ids')
        return result

    def action_view_agreements(self):
        """Smart button "Agreements" on the serial number card."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Agreements'),
            'res_model': 'td.agreement',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.td_agreement_ids.ids)],
            'context': {
                'default_td_lot_ids': [(6, 0, self.ids)],
                'default_partner_id': self.td_last_delivery_partner_id.id,
            },
        }
