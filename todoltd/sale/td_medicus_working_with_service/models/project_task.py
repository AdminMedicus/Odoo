from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    td_agreement_id = fields.Many2one(
        comodel_name='td.agreement',
        string='Agreement',
        ondelete="restrict",
        domain='[("partner_id","=?", partner_id)]'
    )
    td_service_contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Service contact',
        domain=[("type", "=", "service")]
    )
    td_service_contact_phone = fields.Char(
        string='Phone'
    )
    has_service_contact = fields.Boolean(
        related='partner_id.has_service_contact'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('partner_id') and not vals.get('td_service_contact_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.service_contact_id:
                    vals['td_service_contact_id'] = partner.service_contact_id.id
                    vals['td_service_contact_phone'] = partner.service_contact_id.phone
                if partner:
                    vals['email_cc'] = partner.email
        return super().create(vals_list)
