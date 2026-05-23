from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    type = fields.Selection(
        selection_add=[('service', 'Service')]
    )
    has_service_contact = fields.Boolean(
        string='Has Service Contact',
        compute='_compute_has_service_contact',
        store=True
    )
    service_contact_id = fields.Many2one(
        comodel_name='res.partner',
        string='Service Contact',
        compute='_compute_service_contact',
        store=True,
        domain="[('parent_id', '=', id), ('type', '=', 'service')]"
    )

    @api.depends('child_ids.type')
    def _compute_has_service_contact(self):
        for partner in self:
            partner.has_service_contact = any(
                child.type == 'service' for child in partner.child_ids
            )

    @api.depends('child_ids.type')
    def _compute_service_contact(self):
        for partner in self:
            service_contacts = partner.child_ids.filtered(
                lambda c: c.type == 'service'
            )

            if len(service_contacts) == 1:
                partner.service_contact_id = service_contacts.id
            else:
                partner.service_contact_id = False
