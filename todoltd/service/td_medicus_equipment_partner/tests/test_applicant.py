# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import TdEquipmentPartnerCase

EDRPOU_KEY = 'ЄРДПОУ'
SERIAL_KEY = 'Серійний номер обладнання'


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TestApplicant(TdEquipmentPartnerCase):
    """Equipment applicants — AC-28 … AC-38."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lot_l.sudo().td_owner_id = cls.company_a
        cls.Applicant = cls.env['td.equipment.applicant']

    # ── AC-28 ─────────────────────────────────────────────────────────

    def test_ac28_applicant_created_and_reused(self):
        """AC-28 [US-08]: a ticket registers its applicant once per serial number
        and EDRPOU; the next ticket reuses it."""
        first = self._ticket(self.contact_b, self.lot_l)
        applicant = first.td_applicant_id
        self.assertTrue(applicant)
        self.assertEqual(applicant.lot_id, self.lot_l)
        self.assertEqual(applicant.edrpou, self.company_b.company_registry)
        self.assertEqual(applicant.partner_id, self.company_b)
        self.assertFalse(applicant.is_confirmed)

        second = self._ticket(self.contact_b, self.lot_l)
        self.assertEqual(second.td_applicant_id, applicant)
        self.assertEqual(applicant.ticket_count, 2)

    # ── AC-29 ─────────────────────────────────────────────────────────

    def test_ac29_form_keeps_applicant_edrpou(self):
        """AC-29 [US-08]: the website form passes the visitor's EDRPOU on."""
        result = self.env['helpdesk.ticket']._td_autofill_values({
            EDRPOU_KEY: self.unknown_edrpou,
            SERIAL_KEY: self.lot_l.name,
        })
        self.assertEqual(result['record'].get('td_applicant_edrpou'), self.unknown_edrpou)

    def test_ac29_applicant_without_partner(self):
        """AC-29 [US-08]: an applicant unknown to the database is registered by
        its EDRPOU and the form data, without creating a partner."""
        ticket = self._ticket(
            lot=self.lot_l, name='TD-EP Clinic B2',
            td_applicant_edrpou=self.unknown_edrpou,
            partner_name='TD-EP Ivan', partner_phone='+380000000001',
        )
        self.assertEqual(ticket.td_applicant_edrpou, self.unknown_edrpou)
        applicant = ticket.td_applicant_id
        self.assertTrue(applicant)
        self.assertEqual(applicant.edrpou, self.unknown_edrpou)
        self.assertEqual(applicant.company_name, 'TD-EP Clinic B2')
        self.assertEqual(applicant.contact_name, 'TD-EP Ivan')
        self.assertEqual(applicant.phone, '+380000000001')
        self.assertFalse(applicant.partner_id)
        self.assertTrue(ticket.td_is_not_owner)

    def test_ac29_client_edrpou_from_partner(self):
        """AC-29 [US-08]: with a client, the applicant EDRPOU is the client's."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        self.assertEqual(ticket.td_applicant_edrpou, self.company_b.company_registry)

    # ── AC-30 ─────────────────────────────────────────────────────────

    def test_ac30_invalid_edrpou_no_applicant(self):
        """AC-30 [US-08]: no client and an EDRPOU that is not 8 or 10 digits →
        no applicant."""
        ticket = self._ticket(lot=self.lot_l, td_applicant_edrpou='Administrator')
        self.assertFalse(ticket.td_applicant_id)

    def test_ac30_invalid_edrpou_rejected(self):
        """AC-30 [US-08]: an applicant without partner needs a valid EDRPOU."""
        with self.assertRaises(ValidationError):
            self.Applicant.create({'lot_id': self.lot_l.id, 'edrpou': '1234567'})

    # ── AC-31 ─────────────────────────────────────────────────────────

    def test_ac31_unique_pair(self):
        """AC-31 [US-08]: one applicant per serial number and EDRPOU."""
        self.Applicant.create({
            'lot_id': self.lot_l.id, 'edrpou': '90000050', 'company_name': 'TD-EP X',
        })
        with self.assertRaises(ValidationError):
            self.Applicant.create({'lot_id': self.lot_l.id, 'edrpou': '90000050'})

    # ── AC-32 ─────────────────────────────────────────────────────────

    def test_ac32_partner_created_later_is_linked(self):
        """AC-32 [US-08]: a company created later with the same EDRPOU is linked."""
        applicant = self.Applicant.create({
            'lot_id': self.lot_l.id, 'edrpou': '90000098', 'company_name': 'TD-EP New',
        })
        partner = self.env['res.partner'].create({
            'name': 'TD-EP New Clinic', 'is_company': True, 'company_registry': '90000098',
        })
        self.assertEqual(applicant.partner_id, partner)

    def test_ac32_partner_edrpou_written_later_is_linked(self):
        """AC-32 [US-08]: writing the EDRPOU on an existing company links it too."""
        applicant = self.Applicant.create({'lot_id': self.lot_l2.id, 'edrpou': '90000097'})
        self.company_e.write({'company_registry': '90000097'})
        self.assertEqual(applicant.partner_id, self.company_e)

    # ── AC-40 ─────────────────────────────────────────────────────────

    def test_ac40_partner_created_later_becomes_ticket_client(self):
        """AC-40 [US-08]: a company created later with the applicant EDRPOU becomes
        the client of the applicant's open and closed tickets without client."""
        open_ticket = self._ticket(lot=self.lot_l, td_applicant_edrpou='90000095')
        closed_ticket = self._ticket(
            lot=self.lot_l3, td_applicant_edrpou='90000095', stage_id=self.stage_done.id)
        other_ticket = self._ticket(lot=self.lot_l2, td_applicant_edrpou='90000093')

        partner = self.env['res.partner'].create({
            'name': 'TD-EP Late Clinic', 'is_company': True, 'company_registry': '90000095',
        })

        self.assertEqual(open_ticket.partner_id, partner)
        self.assertEqual(closed_ticket.partner_id, partner)
        self.assertEqual(open_ticket.td_applicant_id.partner_id, partner)
        self.assertFalse(other_ticket.partner_id)

    def test_ac40_edrpou_written_later_becomes_ticket_client(self):
        """AC-40 [US-08]: writing the EDRPOU on an existing company does the same,
        and a ticket that already has a client keeps it."""
        ticket = self._ticket(lot=self.lot_l, td_applicant_edrpou='90000094')
        ticket_with_client = self._ticket(self.contact_b, self.lot_l2)
        self.company_e.write({'company_registry': '90000094'})
        self.assertEqual(ticket.partner_id, self.company_e)
        self.assertEqual(ticket_with_client.partner_id, self.contact_b)

    # ── AC-33 ─────────────────────────────────────────────────────────

    def test_ac33_lot_change_repoints(self):
        """AC-33 [US-08]: another serial number moves the ticket to the applicant
        of that serial number; the old applicant stays."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        old = ticket.td_applicant_id
        ticket.write({'lot_id': self.lot_l2.id, 'product_id': self.product_device.id})
        new = ticket.td_applicant_id
        self.assertEqual(new.lot_id, self.lot_l2)
        self.assertEqual(new.partner_id, self.company_b)
        self.assertNotEqual(new, old)
        self.assertTrue(old.exists())

    # ── AC-34 ─────────────────────────────────────────────────────────

    def test_ac34_confirm_applicant(self):
        """AC-34 [US-08]: the engineer confirms the applicant; the notice turns
        into information, the ticket is still "not owner"."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        ticket.with_user(self.user_engineer).action_td_confirm_applicant()
        applicant = ticket.td_applicant_id
        self.assertTrue(applicant.is_confirmed)
        self.assertEqual(applicant.confirmed_uid, self.user_engineer)
        self.assertTrue(applicant.confirmed_date)
        self.assertEqual(ticket.td_owner_notice, 'info')
        self.assertTrue(ticket.td_is_not_owner)

    # ── AC-35 ─────────────────────────────────────────────────────────

    def test_ac35_make_owner(self):
        """AC-35 [US-09]: a manager makes the ticket client the owner."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        ticket.with_user(self.user_manager).action_td_make_owner()
        self.assertEqual(self.lot_l.td_owner_id, self.company_b)
        self.assertFalse(ticket.td_is_not_owner)
        self.assertEqual(ticket.td_owner_notice, 'none')

    def test_ac35_make_owner_needs_manager(self):
        """AC-35 [US-09]: an engineer cannot change the owner."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        with self.assertRaises(AccessError):
            ticket.with_user(self.user_engineer).action_td_make_owner()
        self.assertEqual(self.lot_l.td_owner_id, self.company_a)

    def test_ac35_make_owner_needs_client(self):
        """AC-35 [US-09]: without a client there is nobody to make the owner."""
        ticket = self._ticket(lot=self.lot_l, td_applicant_edrpou=self.unknown_edrpou)
        with self.assertRaises(UserError):
            ticket.with_user(self.user_manager).action_td_make_owner()

    # ── AC-36 ─────────────────────────────────────────────────────────

    def test_ac36_serviced_for_client_filter(self):
        """AC-36 [US-10]: lots the client applied for or owns."""
        self.lot_l2.sudo().td_owner_id = self.company_b
        self._ticket(self.contact_b, self.lot_l)
        lots = self.env['stock.lot'].with_context(td_client_id=self.contact_b.id).search([
            ('td_serviced_for_client', '=', True),
            ('name', '=like', 'TD-EP-SN-%'),
        ])
        self.assertIn(self.lot_l, lots)
        self.assertIn(self.lot_l2, lots)
        self.assertNotIn(self.lot_l3, lots)

    # ── AC-37 ─────────────────────────────────────────────────────────

    def test_ac37_backfill_applicants(self):
        """AC-37 [US-08]: tickets that existed before install get their applicant."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        applicant = ticket.td_applicant_id
        ticket.sudo().write({'td_applicant_id': False})
        applicant.unlink()

        self.env['helpdesk.ticket']._td_backfill_applicants()

        self.assertTrue(ticket.td_applicant_id)
        self.assertEqual(ticket.td_applicant_id.partner_id, self.company_b)
        self.assertFalse(ticket.td_applicant_id.is_confirmed)

    # ── AC-38 ─────────────────────────────────────────────────────────

    def test_ac38_access_rights(self):
        """AC-38 [US-08]: engineers create and confirm applicants, only managers
        delete them."""
        applicant = self.Applicant.with_user(self.user_engineer).create({
            'lot_id': self.lot_l.id, 'edrpou': '90000096', 'company_name': 'TD-EP E1',
        })
        applicant.with_user(self.user_engineer).write({'is_confirmed': True})
        with self.assertRaises(AccessError):
            applicant.with_user(self.user_engineer).unlink()
        applicant.with_user(self.user_manager).unlink()
        self.assertFalse(applicant.exists())
