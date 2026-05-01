from odoo import api, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    td_equipment_id = fields.Many2one(
        comodel_name='stock.lot.report',
        string='Equipment',
        domain="[('partner_id', '=', partner_id)]"
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
                    ('partner_id', '=', rec.partner_id.id),
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
