# -*- coding: utf-8 -*-
from odoo.tests import Form, tagged
from odoo.tools.safe_eval import safe_eval

from .common import TdEquipmentPartnerCase


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TestTicketEquipment(TdEquipmentPartnerCase):
    """Equipment and serial number of the ticket — AC-07 … AC-10."""

    def _ticket_form(self):
        form = Form(self.env['helpdesk.ticket'])
        form.name = 'TD-EP ticket'
        form.team_id = self.team
        return form

    # ── AC-07 ─────────────────────────────────────────────────────────

    def test_ac07_product_domain_not_limited_to_sold(self):
        """AC-07 [US-02]: the product domain is the tracked products, not the
        products sold to the client."""
        domain = self.env['helpdesk.ticket']._fields['product_id'].domain
        self.assertEqual(domain, "[('tracking', '!=', 'none')]")
        self.assertNotIn('suitable_product_ids', domain)

    def test_ac07_product_never_sold_to_client_is_kept(self):
        """AC-07 [US-02]: a product never sold to client B stays on the ticket."""
        form = self._ticket_form()
        form.partner_id = self.contact_b
        form.product_id = self.product_device
        ticket = form.save()
        self.assertEqual(ticket.product_id, self.product_device)

    # ── AC-08 ─────────────────────────────────────────────────────────

    def test_ac08_lot_domain_without_product(self):
        """AC-08 [US-02]: without a product every serial number is selectable;
        with a product only its serial numbers."""
        domain = self.env['helpdesk.ticket']._fields['lot_id'].domain
        test_lots = [('name', '=like', 'TD-EP-SN-%')]
        Lot = self.env['stock.lot']

        lots = Lot.search(safe_eval(domain, {'product_id': False}) + test_lots)
        self.assertIn(self.lot_l, lots)
        self.assertIn(self.lot_other_product, lots)

        lots = Lot.search(
            safe_eval(domain, {'product_id': self.product_device.id}) + test_lots)
        self.assertIn(self.lot_l, lots)
        self.assertNotIn(self.lot_other_product, lots)

    # ── AC-09 ─────────────────────────────────────────────────────────

    def test_ac09_lot_sets_product(self):
        """AC-09 [US-02]: choosing a serial number fills the equipment."""
        form = self._ticket_form()
        form.lot_id = self.lot_l
        self.assertEqual(form.product_id, self.product_device)

    def test_ac09_client_change_keeps_equipment(self):
        """AC-09 [US-02]: changing the client keeps equipment and serial number."""
        form = self._ticket_form()
        form.partner_id = self.contact_a
        form.lot_id = self.lot_l
        form.partner_id = self.contact_b
        self.assertEqual(form.product_id, self.product_device)
        self.assertEqual(form.lot_id, self.lot_l)

    def test_ac09_other_product_clears_lot(self):
        """AC-09 [US-02]: another equipment clears a serial number of a different
        product."""
        form = self._ticket_form()
        form.lot_id = self.lot_l
        form.product_id = self.product_device2
        self.assertFalse(form.lot_id)

    # ── AC-10 ─────────────────────────────────────────────────────────

    def test_ac10_migrate_old_fields(self):
        """AC-10 [US-02]: the install migration copies the serial number of the
        stock.lot.report row into lot_id / product_id."""
        self._deliver(self.lot_l, self.contact_a)
        report_row = self.env['stock.lot.report'].search(
            [('lot_id', '=', self.lot_l.id)], limit=1)
        self.assertTrue(report_row)
        ticket = self._ticket(self.contact_a)
        ticket.write({
            'td_equipment_id': report_row.id,
            'td_serial_number_id': report_row.id,
        })
        self.assertFalse(ticket.lot_id)

        self.env['helpdesk.ticket']._td_migrate_equipment_fields()

        self.assertEqual(ticket.lot_id, self.lot_l)
        self.assertEqual(ticket.product_id, self.product_device)
