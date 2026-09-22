# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


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
