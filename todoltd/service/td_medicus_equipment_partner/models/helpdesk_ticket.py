# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.td_medicus_helpdesk_website_autofill.controllers.website_form import (
    _EDRPOU_KEYS,
    _SERIAL_KEYS,
    _clean,
)

from .td_equipment_applicant import is_valid_edrpou


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # AC-07, AC-08: equipment and serial number do not depend on the client.
    product_id = fields.Many2one(
        domain="[('tracking', '!=', 'none')]",
    )
    lot_id = fields.Many2one(
        domain="[('product_id', '=?', product_id)]",
    )
    td_owner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Equipment Owner',
        readonly=True,
        help='Owner of the serial number. Follows the serial number while the '
             'ticket is open and stays as it was once the ticket is closed.',
    )
    td_owner_edrpou = fields.Char(
        string='Owner EDRPOU',
        related='td_owner_id.company_registry',
    )
    td_is_not_owner = fields.Boolean(
        string='Not Owner',
        compute='_compute_td_is_not_owner',
        store=True,
    )
    td_owner_notice = fields.Selection(
        selection=[
            ('none', 'None'),
            ('warning', 'Warning'),
            ('info', 'Info'),
        ],
        string='Owner Notice',
        compute='_compute_td_owner_notice',
    )
    td_applicant_edrpou = fields.Char(
        string='Applicant EDRPOU',
        help='EDRPOU of the company that asked for the service: the one entered on '
             'the website form, replaced by the EDRPOU of the client once it is set.',
    )
    td_applicant_id = fields.Many2one(
        comodel_name='td.equipment.applicant',
        string='Applicant',
        readonly=True,
        index='btree_not_null',
    )

    # ── Onchanges (AC-09) ─────────────────────────────────────────────

    def onchange_product_id(self):
        """AC-09: helpdesk_stock drops the product when it was never sold to the
        new client. The equipment no longer depends on the client, so keep it."""
        return None

    @api.onchange('lot_id')
    def _onchange_lot_id_td(self):
        """AC-09: the serial number fills the equipment; AC-11: and shows its owner
        before the ticket is saved."""
        for ticket in self:
            if ticket.lot_id:
                ticket.product_id = ticket.lot_id.product_id
            ticket.td_owner_id = ticket.lot_id.td_owner_id

    @api.onchange('lot_id')
    def _onchange_lot_id_agreements_td(self):
        """AC-24: the serial number pulls in its agreements (it replaces the
        onchange of td_medicus_service_report on td_serial_number_id)."""
        for ticket in self:
            ticket.td_agreement_ids = ticket.lot_id.td_agreement_ids

    @api.depends('lot_id', 'partner_id')
    def _compute_td_agreement_domain(self):
        """AC-24: agreements of the serial number and of the client."""
        for ticket in self:
            ticket.td_agreement_domain = self.env['td.agreement']._td_selection_domain(
                ticket.lot_id, ticket.partner_id)

    @api.onchange('product_id')
    def _onchange_product_id_td(self):
        """AC-09: another equipment drops a serial number of a different product."""
        for ticket in self:
            if ticket.lot_id and ticket.lot_id.product_id != ticket.product_id:
                ticket.lot_id = False

    @api.onchange('partner_id')
    def _onchange_partner_id_td_edrpou(self):
        """AC-29: the client's EDRPOU is the applicant's."""
        for ticket in self:
            if ticket.partner_id:
                ticket.td_applicant_edrpou = (
                    ticket.partner_id.commercial_partner_id.company_registry)

    # ── CRUD: owner (AC-11, AC-12) and applicant (AC-28 … AC-33) ──────

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        tickets._td_refresh_owner()
        tickets._td_take_client_edrpou()
        tickets._td_sync_applicant()
        return tickets

    def write(self, vals):
        result = super().write(vals)
        if 'lot_id' in vals:
            self._td_refresh_owner()
        if 'partner_id' in vals:
            self._td_take_client_edrpou()
        if {'lot_id', 'partner_id', 'td_applicant_edrpou'} & set(vals):
            self._td_sync_applicant()
        return result

    def _td_refresh_owner(self):
        """Copy the owner of the serial number onto the ticket."""
        for ticket in self:
            owner = ticket.lot_id.td_owner_id
            if ticket.td_owner_id != owner:
                ticket.sudo().td_owner_id = owner

    def _td_take_client_edrpou(self):
        """AC-29: with a client, the applicant EDRPOU is the client's."""
        for ticket in self.filtered('partner_id'):
            edrpou = ticket.partner_id.commercial_partner_id.company_registry or False
            if ticket.td_applicant_edrpou != edrpou:
                ticket.sudo().td_applicant_edrpou = edrpou

    def _td_sync_applicant(self):
        """AC-28 … AC-33: link the ticket to the applicant of its serial number,
        registering the applicant on its first request. An applicant is the
        client, or, without client, a valid EDRPOU from the website form."""
        Applicant = self.env['td.equipment.applicant'].sudo()
        for ticket in self:
            applicant = Applicant
            client = ticket.partner_id.commercial_partner_id
            edrpou = ticket.td_applicant_edrpou
            if ticket.lot_id and (client or is_valid_edrpou(edrpou)):
                applicant = Applicant._td_find_or_create(ticket.lot_id, client, edrpou, {
                    'company_name': client.name if client else ticket.name,
                    'contact_name': ticket.partner_name,
                    'phone': ticket.partner_phone,
                })
            if ticket.td_applicant_id != applicant:
                ticket.sudo().td_applicant_id = applicant

    # ── Computes ──────────────────────────────────────────────────────

    @api.depends('td_owner_id', 'partner_id.commercial_partner_id', 'td_applicant_edrpou')
    def _compute_td_is_not_owner(self):
        """AC-11: the client belongs to another company than the owner. Contacts
        and delivery addresses of the owner company count as the owner.
        AC-29: without a client, the applicant EDRPOU is compared instead."""
        for ticket in self:
            owner = ticket.td_owner_id.commercial_partner_id
            if not owner:
                ticket.td_is_not_owner = False
            elif ticket.partner_id:
                ticket.td_is_not_owner = ticket.partner_id.commercial_partner_id != owner
            else:
                ticket.td_is_not_owner = bool(
                    ticket.td_applicant_edrpou
                    and ticket.td_applicant_edrpou != owner.company_registry)

    @api.depends('td_is_not_owner', 'td_applicant_id.is_confirmed')
    def _compute_td_owner_notice(self):
        """AC-13: a warning above the ticket when the client is not the owner;
        AC-34: a plain information line once the engineer confirmed the applicant."""
        for ticket in self:
            if not ticket.td_is_not_owner:
                ticket.td_owner_notice = 'none'
            elif ticket.td_applicant_id.is_confirmed:
                ticket.td_owner_notice = 'info'
            else:
                ticket.td_owner_notice = 'warning'

    # ── Website form (AC-16 … AC-19) ──────────────────────────────────

    @api.model
    def _td_autofill_values(self, values):
        """AC-16 … AC-19: resolve the client by EDRPOU and the equipment by serial
        number, independently of each other.

        Nothing is created: an unknown EDRPOU or serial number simply leaves the
        field empty, and the visitor's input stays in the ticket description.

        :return: ``{'record': {field: value}, 'custom': [line]}`` — values for the
            new ticket and extra lines for the "Other Information" block.
        """
        edrpou = self._td_first_form_value(values, _EDRPOU_KEYS)
        serial = self._td_first_form_value(values, _SERIAL_KEYS)
        record, custom = {}, []

        company = self.env['res.partner']
        if edrpou:
            record['td_applicant_edrpou'] = edrpou
            company = self._td_find_company(edrpou)
            if company:
                record['partner_id'] = company.id

        if serial:
            lots = self._td_find_lots(serial)
            if len(lots) > 1:
                related = lots.filtered(
                    lambda lot: (company and lot.td_owner_id == company)
                    or (edrpou and edrpou in lot.td_applicant_ids.mapped('edrpou')))
                if len(related) == 1:
                    lots = related
                else:
                    # AC-19: never guess between models, list them instead.
                    custom += [
                        '%s : %s — %s' % (
                            _('Matching equipment'), lot.product_id.display_name, lot.name)
                        for lot in lots
                    ]
                    lots = lots.browse()
            if len(lots) == 1:
                record.update(lot_id=lots.id, product_id=lots.product_id.id)

        return {'record': record, 'custom': custom}

    @api.model
    def _td_first_form_value(self, values, keys):
        return next((value for value in (_clean(values.get(key)) for key in keys) if value), '')

    @api.model
    def _td_find_company(self, edrpou):
        return self.env['res.partner'].sudo().search([
            ('company_registry', '=', edrpou),
            ('parent_id', '=', False),
        ], order='is_company desc, id', limit=1)

    @api.model
    def _td_find_lots(self, serial):
        """AC-16: exact match only — letter case and leading zeros count.

        Not ``('name', '=', serial)``: with the GS1 barcode nomenclature,
        stock_barcode rewrites ``=`` on a zero-padded digit serial into ``ilike``
        on the unpadded digits ('00001115' → '%1115%', which also matches
        '111555666'). It leaves the ``in`` operator alone, and ``in`` is still an
        exact comparison in SQL.
        """
        # return self.env['stock.lot'].sudo().search([('name', '=', serial)])
        return self.env['stock.lot'].sudo().search([('name', 'in', [serial])])

    # ── Actions (AC-34, AC-35) ────────────────────────────────────────

    def action_td_confirm_applicant(self):
        """AC-34: the engineer confirms that the applicant really services this
        equipment, so its next tickets show information instead of a warning."""
        for ticket in self:
            if not ticket.td_applicant_id:
                raise UserError(_('This ticket has no applicant to confirm.'))
            ticket.td_applicant_id.write({
                'is_confirmed': True,
                'confirmed_uid': self.env.uid,
                'confirmed_date': fields.Datetime.now(),
            })
        return True

    def action_td_make_owner(self):
        """AC-35: the equipment was resold outside Medicus — make the ticket client
        its owner. The owner check of stock.lot.write limits it to managers."""
        for ticket in self:
            if not ticket.partner_id or not ticket.lot_id:
                raise UserError(_(
                    'Set the client and the serial number of the ticket first.'))
            ticket.lot_id.write({'td_owner_id': ticket.partner_id.commercial_partner_id.id})
        return True

    @api.model
    def _td_migrate_equipment_fields(self):
        """AC-10: copy the serial number of the stock.lot.report row kept in
        td_serial_number_id into the standard lot_id / product_id fields."""
        tickets = self.sudo().with_context(active_test=False).search([
            ('td_serial_number_id', '!=', False),
            ('lot_id', '=', False),
        ])
        for ticket in tickets:
            lot = ticket.td_serial_number_id.lot_id
            if lot:
                ticket.write({'lot_id': lot.id, 'product_id': lot.product_id.id})

    @api.model
    def _td_backfill_applicants(self):
        """AC-37: register the applicants of the tickets that existed before
        install, as not confirmed."""
        tickets = self.sudo().with_context(active_test=False).search([('lot_id', '!=', False)])
        tickets._td_take_client_edrpou()
        tickets._td_sync_applicant()
