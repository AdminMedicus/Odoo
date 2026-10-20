# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TdServiceReport(models.Model):
    _inherit = 'td.service.report'

    # AC-21, AC-22: the customer starts as the client of the ticket and is then
    # the report's own value: editable, logged in the ticket chatter through the
    # tracking of td_medicus_service_report, and not following the ticket.
    partner_id = fields.Many2one(
        related=False,
        compute='_compute_td_partner_id',
        store=True,
        precompute=True,
        readonly=False,
        tracking=True,
    )

    @api.depends('ticket_id')
    def _compute_td_partner_id(self):
        for report in self:
            report.partner_id = report.ticket_id.partner_id

    @api.depends('td_lot_id', 'partner_id')
    def _compute_td_agreement_domain(self):
        """AC-24: agreements of the serial number and of the customer."""
        for report in self:
            report.td_agreement_domain = self.env['td.agreement']._td_selection_domain(
                report.td_lot_id, report.partner_id)

    @api.model
    def _td_ticket_from(self, ticket_id):
        ticket = self.env['helpdesk.ticket'].browse(
            ticket_id or self.env.context.get('default_ticket_id'))
        return ticket.exists()

    @api.model
    def default_get(self, fields_list):
        """AC-23: the serial number of the ticket prefills the report."""
        values = super().default_get(fields_list)
        ticket = self._td_ticket_from(values.get('ticket_id'))
        if 'td_lot_id' in fields_list and not values.get('td_lot_id') and ticket.lot_id:
            values['td_lot_id'] = ticket.lot_id.id
        return values

    @api.model_create_multi
    def create(self, vals_list):
        """AC-23: a report created without serial number takes the ticket's."""
        for vals in vals_list:
            if 'td_lot_id' not in vals:
                ticket = self._td_ticket_from(vals.get('ticket_id'))
                if ticket.lot_id:
                    vals['td_lot_id'] = ticket.lot_id.id
        return super().create(vals_list)
