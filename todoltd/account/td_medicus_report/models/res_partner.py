from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    td_partner_short_name = fields.Char(
        string='Short Name'
    )
    contact_address_complete = fields.Char(compute='_td_compute_complete_address', store=False)
    use_in_vendor_refund_report = fields.Boolean(
        string='Use in Vendor Refund Report',
        help='If checked, this contact will be used in the "Vendor Refund Report".'
    )

    @api.onchange('use_in_vendor_refund_report')
    def _onchange_use_in_vendor_refund_report(self):
        """
        When checkbox is activated, deactivate it for all other contacts of the same parent
        """
        if self.use_in_vendor_refund_report and self.parent_id:
            other_contacts = self.search([
                ('parent_id', '=', self.parent_id.id),
                ('type', '=', 'contact'),
                ('id', '!=', self.id or self._origin.id)
            ])
            if other_contacts:
                other_contacts.write({'use_in_vendor_refund_report': False})

    def write(self, vals):
        """
        Override write to handle checkbox logic when saving
        """
        res = super(ResPartner, self).write(vals)
        
        if vals.get('use_in_vendor_refund_report'):
            for partner in self:
                if partner.parent_id and partner.type == 'contact':
                    other_contacts = self.search([
                        ('parent_id', '=', partner.parent_id.id),
                        ('type', '=', 'contact'),
                        ('id', '!=', partner.id),
                        ('use_in_vendor_refund_report', '=', True)
                    ])
                    if other_contacts:
                        other_contacts.write({'use_in_vendor_refund_report': False})
        
        return res

    @api.model
    def create(self, vals):
        """
        Override create to handle checkbox logic when creating
        """
        res = super(ResPartner, self).create(vals)
        
        if vals.get('use_in_vendor_refund_report') and res.parent_id and res.type == 'contact':
            other_contacts = self.search([
                ('parent_id', '=', res.parent_id.id),
                ('type', '=', 'contact'),
                ('id', '!=', res.id),
                ('use_in_vendor_refund_report', '=', True)
            ])
            if other_contacts:
                other_contacts.write({'use_in_vendor_refund_report': False})
        
        return res

    def _td_compute_complete_address(self):
        for record in self:
            record.contact_address_complete = ''
            if record.zip:
                record.contact_address_complete += record.zip + ', '
            if record.country_id:
                record.contact_address_complete += record.country_id.name + ', '
            if record.state_id:
                record.contact_address_complete += record.state_id.name + ', '
            if record.city:
                record.contact_address_complete += record.city + ', '
            if record.street:
                record.contact_address_complete += record.street + ', '
            if record.street2:
                record.contact_address_complete += record.street2 + ', '
            record.contact_address_complete = record.contact_address_complete.strip().strip(',')
