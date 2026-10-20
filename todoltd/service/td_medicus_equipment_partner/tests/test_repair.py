# -*- coding: utf-8 -*-
from odoo.tests import Form, tagged

from .common import TdEquipmentPartnerCase


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TestRepair(TdEquipmentPartnerCase):
    """Repair and quotation of a ticket — AC-26, AC-27."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lot_l.sudo().td_owner_id = cls.company_a
        cls.ticket = cls._ticket(cls.contact_b, cls.lot_l)

    # ── AC-26 ─────────────────────────────────────────────────────────

    def test_ac26_repair_defaults_from_ticket(self):
        """AC-26 [US-07]: the Repair button of the ticket uses the ticket's client,
        equipment and serial number, not the owner of the serial number."""
        defaults = self.ticket._prepare_repairs_default_value()
        self.assertEqual(defaults['default_partner_id'], self.contact_b.id)
        self.assertEqual(defaults['default_lot_id'], self.lot_l.id)
        self.assertEqual(defaults['default_product_id'], self.product_device.id)

    # ── AC-27 ─────────────────────────────────────────────────────────

    def test_ac27_quotation_for_ticket_client(self):
        """AC-27 [US-07]: the quotation of that repair is made for the ticket client."""
        context = self.ticket._prepare_repairs_default_value()
        repair = Form(self.env['repair.order'].with_context(context)).save()
        self.assertEqual(repair.partner_id, self.contact_b)
        self.assertEqual(repair.lot_id, self.lot_l)
        repair.action_create_sale_order()
        self.assertEqual(repair.sale_order_id.partner_id, self.contact_b)
        self.assertNotEqual(repair.sale_order_id.partner_id.commercial_partner_id,
                            self.company_a)
