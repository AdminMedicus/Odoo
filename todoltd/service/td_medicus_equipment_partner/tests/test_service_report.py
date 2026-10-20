# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import Form, tagged

from .common import TdEquipmentPartnerCase


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TestServiceReport(TdEquipmentPartnerCase):
    """Service report customer and agreements — AC-21 … AC-25."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lot_l.sudo().td_owner_id = cls.company_a
        Agreement = cls.env['td.agreement']
        # Created in reverse of the expected order, so the default order (id)
        # cannot pass AC-25 by accident.
        cls.agreement_z = Agreement.create({
            'name': 'TD-EP Z purchase', 'number': 'TD-EP-Z',
            'partner_id': cls.company_a.id,
            'td_lot_ids': [Command.link(cls.lot_l.id)],
        })
        cls.agreement_y = Agreement.create({
            'name': 'TD-EP Y service', 'number': 'TD-EP-Y',
            'partner_id': cls.company_b.id,
        })
        cls.agreement_x = Agreement.create({
            'name': 'TD-EP X service', 'number': 'TD-EP-X',
            'partner_id': cls.company_b.id,
            'td_lot_ids': [Command.link(cls.lot_l.id)],
        })
        cls.agreement_w = Agreement.create({
            'name': 'TD-EP W other', 'number': 'TD-EP-W',
            'partner_id': cls.company_e.id,
        })
        cls.ticket = cls._ticket(cls.contact_b, cls.lot_l)

    def _report(self, **vals):
        return self.env['td.service.report'].create(dict(ticket_id=self.ticket.id, **vals))

    # ── AC-21 ─────────────────────────────────────────────────────────

    def test_ac21_customer_defaults_to_ticket_client(self):
        """AC-21 [US-06]: a new report takes the client of the ticket."""
        self.assertEqual(self._report().partner_id, self.contact_b)

    def test_ac21_customer_editable_and_logged(self):
        """AC-21 [US-06]: the customer can be changed, and the change is noted in
        the ticket chatter."""
        report = self._report()
        report.write({'partner_id': self.company_e.id})
        self.assertEqual(report.partner_id, self.company_e)
        self.assertEqual(self.ticket.partner_id, self.contact_b,
                         'changing the report customer does not touch the ticket')
        body = self.ticket.message_ids[0].body
        self.assertIn('Customer', body)
        self.assertIn(self.contact_b.display_name, body)
        self.assertIn(self.company_e.display_name, body)

    # ── AC-22 ─────────────────────────────────────────────────────────

    def test_ac22_customer_not_following_ticket(self):
        """AC-22 [US-06]: a later change of the ticket client leaves the report."""
        report = self._report()
        self.ticket.partner_id = self.company_e
        self.assertEqual(report.partner_id, self.contact_b)

    # ── AC-23 ─────────────────────────────────────────────────────────

    def test_ac23_lot_from_ticket_default_get(self):
        """AC-23 [US-06]: the report wizard prefills the serial number of the ticket."""
        defaults = self.env['td.service.report'].with_context(
            default_ticket_id=self.ticket.id).default_get(['td_lot_id'])
        self.assertEqual(defaults.get('td_lot_id'), self.lot_l.id)

    def test_ac23_lot_from_ticket_create(self):
        """AC-23 [US-06]: a report created without serial number takes the ticket's."""
        self.assertEqual(self._report().td_lot_id, self.lot_l)

    # ── AC-24 ─────────────────────────────────────────────────────────

    def _domain_agreements(self, domain):
        tests = ('number', '=like', 'TD-EP-%')
        return self.env['td.agreement'].search(list(domain) + [tests])

    def test_ac24_ticket_agreement_domain(self):
        """AC-24 [US-06]: the ticket offers the agreements of its serial number
        and of its client."""
        agreements = self._domain_agreements(self.ticket.td_agreement_domain)
        self.assertEqual(
            agreements, self.agreement_x | self.agreement_y | self.agreement_z)

    def test_ac24_report_agreement_domain(self):
        """AC-24 [US-06]: the report offers the agreements of its serial number
        and of its customer."""
        report = self._report()
        agreements = self._domain_agreements(report.td_agreement_domain)
        self.assertEqual(
            agreements, self.agreement_x | self.agreement_y | self.agreement_z)

    def test_ac24_lot_onchange_fills_agreements(self):
        """AC-24 [US-06]: choosing the serial number pulls in its agreements."""
        form = Form(self.env['helpdesk.ticket'])
        form.name = 'TD-EP ticket'
        form.team_id = self.team
        form.partner_id = self.contact_b
        form.lot_id = self.lot_l
        self.assertEqual(
            set(form.td_agreement_ids.ids), {self.agreement_x.id, self.agreement_z.id})

    # ── AC-25 ─────────────────────────────────────────────────────────

    def test_ac25_agreement_order_and_label(self):
        """AC-25 [US-06]: the client's agreements of the serial number first, then
        the client's other agreements, then those of other counterparties; every
        row names its counterparty."""
        Agreement = self.env['td.agreement'].with_context(
            td_agreement_client_id=self.contact_b.id,
            td_agreement_lot_id=self.lot_l.id,
        )
        result = Agreement.name_search(
            '', args=[('id', 'in', (self.agreement_x | self.agreement_y | self.agreement_z).ids)],
            limit=10)
        self.assertEqual(
            [agreement_id for agreement_id, _name in result],
            [self.agreement_x.id, self.agreement_y.id, self.agreement_z.id])
        labels = dict(result)
        self.assertTrue(labels[self.agreement_x.id].endswith(' — TD-EP Company B'))
        self.assertTrue(labels[self.agreement_z.id].endswith(' — TD-EP Company A'))

    def test_ac25_no_context_unchanged(self):
        """AC-25 [US-06]: without the context the label stays the plain name."""
        self.assertEqual(self.agreement_x.display_name, 'TD-EP X service')
