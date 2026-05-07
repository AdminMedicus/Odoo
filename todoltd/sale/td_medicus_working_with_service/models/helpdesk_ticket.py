from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    td_equipment_id = fields.Many2one(
        comodel_name='stock.lot.report',
        string='Equipment',
        domain="[('partner_id', 'child_of', partner_id)]"
    )
    td_serial_number_id = fields.Many2one(
        comodel_name='stock.lot.report',
        string='Serial Number'
    )
    td_serial_domain = fields.Binary(
        compute='_compute_td_serial_domain',
        readonly=True
    )

    @api.depends('partner_id', 'td_equipment_id')
    def _compute_td_serial_domain(self):
        for rec in self:
            if rec.partner_id and rec.td_equipment_id:
                rec.td_serial_domain = [
                    ('partner_id', 'child_of', rec.partner_id.id),
                    ('product_id', '=', rec.td_equipment_id.product_id.id),
                ]
            else:
                rec.td_serial_domain = [('id', '=', False)]

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            rec.td_equipment_id = False
            rec.td_serial_number_id = False

    @api.onchange('td_equipment_id')
    def _onchange_equipment(self):
        for rec in self:
            rec.td_serial_number_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'partner_id' in vals and vals['partner_id']:
                partner = self.env['res.partner'].sudo().browse(vals['partner_id'])
                if partner:
                    vals['email_cc'] = partner.email

        return super().create(vals_list)
