# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TdEquipmentPartnerCase


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TestLotOwner(TdEquipmentPartnerCase):
    """Owner of a serial number — AC-01 … AC-06."""

    # ── AC-01 ─────────────────────────────────────────────────────────

    def test_ac01_sale_delivery_sets_owner(self):
        """AC-01 [US-01]: Given a serial lot and an outgoing transfer of type
        'exp_inv' to a contact of company A, when it is validated, then the
        owner of the lot is company A."""
        self.assertFalse(self.lot_l.td_owner_id)
        picking = self._deliver(self.lot_l, self.contact_a, 'exp_inv')
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self.lot_l.td_owner_id, self.company_a)

    def test_ac01_delivery_without_document_type_sets_owner(self):
        """AC-01 [US-01]: an outgoing transfer without implementation document
        is a sale as well."""
        self._deliver(self.lot_l, self.contact_a, False)
        self.assertEqual(self.lot_l.td_owner_id, self.company_a)

    # ── AC-02 ─────────────────────────────────────────────────────────

    def test_ac02_storage_act_keeps_owner(self):
        """AC-02 [US-01]: an act of responsible storage does not change the owner."""
        self.lot_l.sudo().td_owner_id = self.company_a
        picking = self._deliver(self.lot_l, self.company_e, 'act_res_st')
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self.lot_l.td_owner_id, self.company_a)

    def test_ac02_movement_keeps_empty_owner(self):
        """AC-02 [US-01]: a movement does not set an owner."""
        picking = self._deliver(self.lot_l, self.company_e, 'move')
        self.assertEqual(picking.state, 'done')
        self.assertFalse(self.lot_l.td_owner_id)

    # ── AC-03 ─────────────────────────────────────────────────────────

    def _flush_tracking(self):
        self.env.flush_all()
        self.env.cr.precommit.run()

    def test_ac03_resale_changes_owner_and_tracks(self):
        """AC-03 [US-01]: a lot owned by A sold to E gets owner E, and the lot
        chatter tracks the change A → E."""
        self._deliver(self.lot_l, self.contact_a)
        self._flush_tracking()
        self.assertEqual(self.lot_l.td_owner_id, self.company_a)

        self._return_to_stock_for_resale()
        self._deliver(self.lot_l, self.company_e)
        self._flush_tracking()
        self.assertEqual(self.lot_l.td_owner_id, self.company_e)
        owner_field = self.env['ir.model.fields']._get('stock.lot', 'td_owner_id')
        tracking = self.lot_l.message_ids.tracking_value_ids.filtered(
            lambda t: t.field_id == owner_field)
        self.assertIn(
            (self.company_a.display_name, self.company_e.display_name),
            [(t.old_value_char, t.new_value_char) for t in tracking],
        )

    def _return_to_stock_for_resale(self):
        """The unit comes back to stock without a return of the sale (e.g. a
        buy-back), so only the new sale decides the owner."""
        self.env['stock.quant']._update_available_quantity(
            self.lot_l.product_id, self.customer_location, -1.0, lot_id=self.lot_l)

    # ── AC-04 ─────────────────────────────────────────────────────────

    def test_ac04_return_clears_owner(self):
        """AC-04 [US-01]: the return of the sale that set owner A clears the owner."""
        sale = self._deliver(self.lot_l, self.contact_a)
        self.assertEqual(self.lot_l.td_owner_id, self.company_a)
        return_picking = self._return(sale, self.lot_l)
        self.assertEqual(return_picking.state, 'done')
        self.assertFalse(self.lot_l.td_owner_id)

    def test_ac04_return_keeps_newer_owner(self):
        """AC-04 [US-01]: when the owner already became E, the return of A's
        sale leaves E."""
        sale = self._deliver(self.lot_l, self.contact_a)
        self.lot_l.sudo().td_owner_id = self.company_e
        self._return(sale, self.lot_l)
        self.assertEqual(self.lot_l.td_owner_id, self.company_e)

    # ── AC-05 ─────────────────────────────────────────────────────────

    def test_ac05_backfill_replays_history(self):
        """AC-05 [US-01]: the install backfill replays sales, storage acts and
        returns in the order they were done."""
        self._deliver(self.lot_l, self.contact_a)                      # → A
        sale_l2 = self._deliver(self.lot_l2, self.contact_a)
        self._return(sale_l2, self.lot_l2)                             # → none
        self._deliver(self.lot_l3, self.company_e, 'act_res_st')       # → none
        self._deliver(self.lot_other_product, self.contact_a)
        self.env['stock.quant']._update_available_quantity(
            self.product_device2, self.customer_location, -1.0,
            lot_id=self.lot_other_product)
        self._deliver(self.lot_other_product, self.company_e)          # → E
        lots = self.lot_l | self.lot_l2 | self.lot_l3 | self.lot_other_product
        lots.sudo().td_owner_id = self.company_b  # state before install: unknown

        self.env['stock.lot']._td_backfill_owners()

        self.assertEqual(self.lot_l.td_owner_id, self.company_a)
        self.assertFalse(self.lot_l2.td_owner_id)
        self.assertEqual(self.lot_l3.td_owner_id, self.company_b,
                         'a lot without any sale keeps what it had')
        self.assertEqual(self.lot_other_product.td_owner_id, self.company_e)

    # ── AC-06 ─────────────────────────────────────────────────────────

    def test_ac06_owner_write_needs_manager(self):
        """AC-06 [US-09]: a user without the helpdesk / inventory manager groups
        cannot change the owner; a helpdesk manager can."""
        lot_as_engineer = self.lot_l.with_user(self.user_engineer)
        lot_as_engineer.write({'ref': 'TD-EP-REF'})  # the lot itself is editable
        with self.assertRaises(AccessError):
            lot_as_engineer.write({'td_owner_id': self.company_a.id})
        self.lot_l.with_user(self.user_manager).write({'td_owner_id': self.company_a.id})
        self.assertEqual(self.lot_l.td_owner_id, self.company_a)

    def test_ac06_engineer_delivery_still_sets_owner(self):
        """AC-06 [US-09]: the automatic update of a sale delivery is not a manual
        change, so it works for a user without the manager groups."""
        # td_medicus_1c_integration creates the daily date range of its delivery
        # sequence on the first validation of the day, which needs admin rights:
        # let the administrator validate the first delivery of the day.
        self._deliver(self.lot_l2, self.contact_a)
        picking = self._deliver(self.lot_l, self.contact_a, user=self.user_engineer)
        self.assertEqual(picking.state, 'done')
        self.assertEqual(self.lot_l.td_owner_id, self.company_a)
