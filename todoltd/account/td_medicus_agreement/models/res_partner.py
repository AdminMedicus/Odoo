from odoo import models, fields, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    count_agreement = fields.Integer(
        default=0,
        compute='_compute_count_agreement'
    )

    def action_view_agreements(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Agreements'),
            'res_model': 'td.agreement',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('partner_id', '=', self.id)],
        }

    def _compute_count_agreement(self):
        for partner in self:
            records = self.env['td.agreement'].search([
                ('partner_id', '=', partner.id)
            ])
            partner.count_agreement = len(records)
