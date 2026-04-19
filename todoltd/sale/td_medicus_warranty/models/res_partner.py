from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    td_warranty_ids = fields.One2many(
        comodel_name='td.warranty.record',
        inverse_name='partner_id',
        string='Warranties',
        help='All warranties for this customer.'
    )
    td_warranty_count = fields.Integer(
        string='Warranty Count',
        compute='_compute_td_warranty_count'
    )

    @api.depends('td_warranty_ids')
    def _compute_td_warranty_count(self):
        """Count warranties for this customer."""
        for partner in self:
            partner.td_warranty_count = len(partner.td_warranty_ids)

    def action_view_warranties(self):
        """Open warranties view for this customer."""
        self.ensure_one()
        action = self.env.ref('td_medicus_warranty.action_td_warranty_record').read()[0]
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {
            'default_partner_id': self.id,
        }
        return action
