# -*- coding: utf-8 -*-
from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._td_link_applicants()
        return partners

    def write(self, vals):
        result = super().write(vals)
        if 'company_registry' in vals or 'parent_id' in vals:
            self._td_link_applicants()
        return result

    def _td_link_applicants(self):
        """A company that appears later with the EDRPOU of an applicant becomes
        the partner of that applicant (AC-32) and the client of its tickets that
        have no client yet (AC-40)."""
        companies = self.filtered(lambda partner: not partner.parent_id and partner.company_registry)
        if not companies:
            return
        applicants = self.env['td.equipment.applicant'].sudo().search([
            ('partner_id', '=', False),
            ('edrpou', 'in', companies.mapped('company_registry')),
        ])
        for applicant in applicants:
            company = companies.filtered(
                lambda partner: partner.company_registry == applicant.edrpou)[:1]
            applicant.partner_id = company
            applicant.ticket_ids.filtered(lambda ticket: not ticket.partner_id).partner_id = company
