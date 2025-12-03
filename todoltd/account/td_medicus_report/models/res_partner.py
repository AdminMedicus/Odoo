from odoo import _, api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    td_license_number = fields.Char(
        string='License Number'
    )
    td_license_date = fields.Date(
        string='License Date'
    )
    td_license_issued_by = fields.Char(
        string='License Issued By'
    )
    # td_short_name = fields.Char(
    #     string='Short Name',
    #     store=True
    # )
    contact_address_complete = fields.Char(compute='_td_compute_complete_address', store=False)


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
    