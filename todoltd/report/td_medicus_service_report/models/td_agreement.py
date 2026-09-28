# -*- coding: utf-8 -*-
from odoo import api, fields, models

from .relation_chatter import post_relation_changes, relation_snapshots


class TdAgreement(models.Model):
    _inherit = 'td.agreement'

    td_lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        relation='td_agreement_stock_lot_rel',
        column1='agreement_id',
        column2='lot_id',
        string='Equipment Serial Number',
        help='Equipment this agreement covers. One customer may own several '
             'units and each unit has its own set of agreements.',
    )

    def init(self):
        """Align existing contracts on both fresh installs and module upgrades."""
        super().init()
        self.env.cr.execute("""
            UPDATE td_agreement
               SET agreement_number = number
             WHERE (agreement_number IS NULL OR agreement_number = '')
               AND number IS NOT NULL AND number != ''
        """)
        self.env.cr.execute("""
            UPDATE td_agreement
               SET number = agreement_number
             WHERE agreement_number IS NOT NULL AND agreement_number != ''
               AND number IS DISTINCT FROM agreement_number
        """)

    @staticmethod
    def _matching_numbers(vals):
        values = dict(vals)
        if 'agreement_number' in values:
            values['number'] = values['agreement_number']
        elif 'number' in values:
            values['agreement_number'] = values['number']
        return values

    @api.model_create_multi
    def create(self, vals_list):
        agreements = super().create([self._matching_numbers(vals) for vals in vals_list])
        for agreement in agreements:
            # The base agreement module may assign a number inside its create.
            if agreement.agreement_number != agreement.number:
                preferred = agreement.agreement_number or agreement.number
                if preferred:
                    agreement.write({'agreement_number': preferred})
        post_relation_changes(agreements, 'td_lot_ids',
                              inverse_field_name='td_agreement_ids')
        return agreements

    def write(self, vals):
        previous = (relation_snapshots(self, 'td_lot_ids')
                    if 'td_lot_ids' in vals else None)
        result = super().write(self._matching_numbers(vals))
        if previous is not None:
            post_relation_changes(self, 'td_lot_ids', previous,
                                  inverse_field_name='td_agreement_ids')
        return result
