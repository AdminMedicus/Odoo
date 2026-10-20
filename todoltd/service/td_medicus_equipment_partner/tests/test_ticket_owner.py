# -*- coding: utf-8 -*-
from lxml import etree

from odoo.tests import tagged

from .common import TdEquipmentPartnerCase


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TestTicketOwner(TdEquipmentPartnerCase):
    """Owner and the "not owner" notice of the ticket — AC-11 … AC-14."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lot_l.sudo().td_owner_id = cls.company_a

    # ── AC-11 ─────────────────────────────────────────────────────────

    def test_ac11_other_company_is_not_owner(self):
        """AC-11 [US-03]: client of company B on a lot owned by A."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        self.assertEqual(ticket.td_owner_id, self.company_a)
        self.assertTrue(ticket.td_is_not_owner)

    def test_ac11_contact_of_owner_is_owner(self):
        """AC-11 [US-03]: a contact of the owner company is the owner."""
        ticket = self._ticket(self.contact_a, self.lot_l)
        self.assertEqual(ticket.td_owner_id, self.company_a)
        self.assertFalse(ticket.td_is_not_owner)

    def test_ac11_lot_without_owner(self):
        """AC-11 [US-03]: no owner on the lot, no owner and no flag on the ticket."""
        ticket = self._ticket(self.contact_b, self.lot_l2)
        self.assertFalse(ticket.td_owner_id)
        self.assertFalse(ticket.td_is_not_owner)

    # ── AC-12 ─────────────────────────────────────────────────────────

    def test_ac12_open_ticket_follows_owner(self):
        """AC-12 [US-03]: an open ticket follows the new owner of its lot."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        self.lot_l.sudo().td_owner_id = self.company_e
        self.assertEqual(ticket.td_owner_id, self.company_e)
        self.assertTrue(ticket.td_is_not_owner)
        self.lot_l.sudo().td_owner_id = self.company_b
        self.assertEqual(ticket.td_owner_id, self.company_b)
        self.assertFalse(ticket.td_is_not_owner)

    def test_ac12_folded_ticket_frozen(self):
        """AC-12 [US-03]: a ticket in a folded stage keeps its owner and flag."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        ticket.stage_id = self.stage_done
        self.lot_l.sudo().td_owner_id = self.company_b
        self.assertEqual(ticket.td_owner_id, self.company_a)
        self.assertTrue(ticket.td_is_not_owner)

    # ── AC-13 ─────────────────────────────────────────────────────────

    def test_ac13_notice_warning_for_not_owner(self):
        """AC-13 [US-03]: not owner and no confirmed applicant → warning."""
        ticket = self._ticket(self.contact_b, self.lot_l)
        self.assertEqual(ticket.td_owner_notice, 'warning')

    def test_ac13_notice_none_for_owner(self):
        """AC-13 [US-03]: the owner itself → no notice."""
        ticket = self._ticket(self.contact_a, self.lot_l)
        self.assertEqual(ticket.td_owner_notice, 'none')

    # ── AC-14 ─────────────────────────────────────────────────────────

    def test_ac14_search_filter(self):
        """AC-14 [US-04]: the ticket search view offers "Applicant ≠ Owner"."""
        arch = self.env['helpdesk.ticket'].get_view(view_type='search')['arch']
        nodes = etree.fromstring(arch).xpath("//filter[@name='td_filter_not_owner']")
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].get('domain'), "[('td_is_not_owner', '=', True)]")
