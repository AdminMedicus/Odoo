# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

from .relation_chatter import post_relation_changes, relation_snapshots


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    td_service_report_ids = fields.One2many(
        comodel_name='td.service.report',
        inverse_name='ticket_id',
        string='Service Reports',
    )
    td_service_report_count = fields.Integer(
        string='Service Reports Count',
        compute='_compute_td_service_report_count',
    )
    td_agreement_ids = fields.Many2many(
        comodel_name='td.agreement',
        relation='td_helpdesk_ticket_agreement_rel',
        column1='ticket_id',
        column2='agreement_id',
        string='Agreement',
        help='Agreements related to the selected piece of equipment.',
    )
    td_agreement_domain = fields.Binary(
        string='Agreement Domain',
        compute='_compute_td_agreement_domain',
        readonly=True,
    )

    @api.depends('td_service_report_ids')
    def _compute_td_service_report_count(self):
        for ticket in self:
            ticket.td_service_report_count = len(ticket.td_service_report_ids)

    @api.depends('td_serial_number_id', 'td_serial_number_id.lot_id', 'partner_id')
    def _compute_td_agreement_domain(self):
        """Only the agreements of the chosen equipment can be picked
        (section 4 of the specification)."""
        for ticket in self:
            lot = ticket.td_serial_number_id.lot_id
            if lot:
                ticket.td_agreement_domain = [('td_lot_ids', 'in', lot.ids)]
            elif ticket.partner_id:
                ticket.td_agreement_domain = [('partner_id', 'child_of', ticket.partner_id.id)]
            else:
                ticket.td_agreement_domain = []

    @api.onchange('td_serial_number_id')
    def _onchange_td_serial_number_agreements(self):
        """Pull in all the agreements of the selected device and drop the ones
        that belong to the previously selected device."""
        for ticket in self:
            lot = ticket.td_serial_number_id.lot_id
            ticket.td_agreement_ids = lot.td_agreement_ids if lot else False

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        post_relation_changes(tickets, 'td_agreement_ids')
        return tickets

    def write(self, vals):
        previous = (relation_snapshots(self, 'td_agreement_ids')
                    if 'td_agreement_ids' in vals else None)
        result = super().write(vals)
        if previous is not None:
            post_relation_changes(self, 'td_agreement_ids', previous)
        return result

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_create_service_report(self):
        """The big "Generate report" button of the ticket: behaves like "New"
        in the service report list and opens a fresh report in the wizard.

        The record is created only when the engineer saves the dialog, so a
        misclick does not leave an empty report behind.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Service Report'),
            'res_model': 'td.service.report',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'td_medicus_service_report.view_td_service_report_form').id,
            'target': 'new',
            'context': {'default_ticket_id': self.id},
        }

    def action_view_service_reports(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Service Reports'),
            'res_model': 'td.service.report',
            'view_mode': 'list,form',
            'domain': [('ticket_id', '=', self.id)],
            'context': {'default_ticket_id': self.id},
        }
