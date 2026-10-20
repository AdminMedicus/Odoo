# -*- coding: utf-8 -*-
from odoo.tests import tagged

from odoo.addons.td_medicus_equipment_partner.hooks import post_init_hook

from .common import TdEquipmentPartnerCase


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TestInstallHook(TdEquipmentPartnerCase):
    """The install hook wires the backfills of AC-05, AC-10 and AC-37."""

    def test_hook_backfills_existing_data(self):
        """A closed ticket of a serial number sold to A, made before install,
        gets the lot owner, its owner on the ticket and its applicant."""
        self._deliver(self.lot_l, self.contact_a)
        ticket = self._ticket(self.contact_b, self.lot_l, stage_id=self.stage_done.id)
        # State before install: none of the module's data exists yet.
        self.lot_l.sudo().td_owner_id = False
        applicant = ticket.td_applicant_id
        ticket.sudo().write({'td_applicant_id': False, 'td_owner_id': False})
        applicant.unlink()

        post_init_hook(self.env)

        self.assertEqual(self.lot_l.td_owner_id, self.company_a)
        self.assertEqual(ticket.td_owner_id, self.company_a)
        self.assertTrue(ticket.td_is_not_owner)
        self.assertEqual(ticket.td_applicant_id.partner_id, self.company_b)
