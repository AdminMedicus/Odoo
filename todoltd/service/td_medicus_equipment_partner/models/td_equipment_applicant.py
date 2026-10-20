# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# ЄДРПОУ of a legal entity (8 digits) or РНОКПП of a sole proprietor (10 digits).
EDRPOU_RE = re.compile(r'\d{8}|\d{10}')


def is_valid_edrpou(code):
    return bool(code and EDRPOU_RE.fullmatch(code))


class TdEquipmentApplicant(models.Model):
    _name = 'td.equipment.applicant'
    _description = 'Equipment Applicant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'lot_id, id'
    _rec_name = 'company_name'

    lot_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Serial Number',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Equipment',
        related='lot_id.product_id',
        store=True,
    )
    edrpou = fields.Char(
        string='EDRPOU',
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
    )
    company_name = fields.Char(
        string='Company Name',
    )
    contact_name = fields.Char(
        string='Contact',
    )
    phone = fields.Char(
        string='Phone',
    )
    ticket_ids = fields.One2many(
        comodel_name='helpdesk.ticket',
        inverse_name='td_applicant_id',
        string='Tickets',
    )
    ticket_count = fields.Integer(
        string='Tickets Count',
        compute='_compute_ticket_count',
    )
    is_confirmed = fields.Boolean(
        string='Confirmed',
        default=False,
        tracking=True,
    )
    confirmed_uid = fields.Many2one(
        comodel_name='res.users',
        string='Confirmed By',
    )
    confirmed_date = fields.Datetime(
        string='Confirmed On',
    )

    @api.depends('ticket_ids')
    def _compute_ticket_count(self):
        """AC-28"""
        for applicant in self:
            applicant.ticket_count = len(applicant.ticket_ids)

    @api.constrains('edrpou', 'partner_id')
    def _check_edrpou(self):
        """AC-30: an applicant that is not in the database is identified by a
        valid EDRPOU."""
        for applicant in self:
            if not applicant.partner_id and not is_valid_edrpou(applicant.edrpou):
                raise ValidationError(_(
                    'An applicant without a partner needs an EDRPOU of 8 or 10 digits.'))

    @api.constrains('lot_id', 'edrpou', 'partner_id')
    def _check_unique_pair(self):
        """AC-31: one applicant per serial number and company."""
        for applicant in self:
            if self.search_count([('id', '!=', applicant.id)] + applicant._td_pair_domain(
                    applicant.lot_id, applicant.partner_id, applicant.edrpou), limit=1):
                raise ValidationError(_(
                    'The company %(company)s is already an applicant of the serial '
                    'number %(serial)s.',
                    company=applicant.display_name, serial=applicant.lot_id.name))

    @api.model
    def _td_pair_domain(self, lot, partner, edrpou):
        if edrpou:
            return [('lot_id', '=', lot.id), ('edrpou', '=', edrpou)]
        return [('lot_id', '=', lot.id), ('edrpou', '=', False),
                ('partner_id', '=', partner.id)]

    @api.model
    def _td_find_or_create(self, lot, partner, edrpou, vals):
        """AC-28: return the applicant of the (lot, edrpou) pair — or of the
        (lot, partner) pair when the partner has no EDRPOU — creating it from
        ``vals`` when missing. A partner found later completes the record."""
        partner = partner.commercial_partner_id
        edrpou = partner.company_registry if partner else edrpou
        applicant = self.search(self._td_pair_domain(lot, partner, edrpou), limit=1)
        if not applicant:
            applicant = self.create(dict(
                vals, lot_id=lot.id, edrpou=edrpou or False, partner_id=partner.id))
        elif partner and not applicant.partner_id:
            applicant.partner_id = partner
        return applicant
