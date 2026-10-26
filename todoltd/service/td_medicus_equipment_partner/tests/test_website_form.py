# -*- coding: utf-8 -*-
from odoo.addons.website.tools import MockRequest
from odoo.tests import tagged

from odoo.addons.td_medicus_equipment_partner.controllers.website_form import (
    WebsiteFormEquipment,
)

from .common import TdEquipmentPartnerCase

# Labels of the custom inputs of the Medicus ticket form.
EDRPOU_KEY = 'ЄРДПОУ'
SERIAL_KEY = 'Серійний номер обладнання'


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TestWebsiteForm(TdEquipmentPartnerCase):
    """Website ticket form — AC-16 … AC-20."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lot_l.sudo().td_owner_id = cls.company_a
        Lot = cls.env['stock.lot']
        cls.lot_dup1 = Lot.create({
            'name': 'TD-EP-DUP-1', 'product_id': cls.product_device.id,
            'company_id': cls.company.id,
        })
        cls.lot_dup2 = Lot.create({
            'name': 'TD-EP-DUP-1', 'product_id': cls.product_device2.id,
            'company_id': cls.company.id,
        })

    def _autofill(self, **values):
        return self.env['helpdesk.ticket']._td_autofill_values(values)

    # ── AC-16 ─────────────────────────────────────────────────────────

    def test_ac16_serial_and_edrpou_independent(self):
        """AC-16 [US-05]: S/N of a lot owned by A and EDRPOU of B → client B,
        equipment of the lot, and the ticket is marked "not owner"."""
        result = self._autofill(**{
            EDRPOU_KEY: self.company_b.company_registry,
            SERIAL_KEY: self.lot_l.name,
        })
        record = result['record']
        self.assertEqual(record.get('partner_id'), self.company_b.id)
        self.assertEqual(record.get('lot_id'), self.lot_l.id)
        self.assertEqual(record.get('product_id'), self.product_device.id)

        ticket = self._ticket(name='TD-EP form ticket', **record)
        self.assertTrue(ticket.td_is_not_owner)

    def test_ac16_serial_normalized(self):
        """AC-16 [US-05]: extra spaces and invisible characters around the serial
        number do not stop the match."""
        result = self._autofill(**{SERIAL_KEY: '  TD-EP-SN-001​ '})
        self.assertEqual(result['record'].get('lot_id'), self.lot_l.id)

    def test_ac16_serial_leading_zeros(self):
        """AC-16 [US-05]: leading zeros are part of the serial number: typed in
        full they match, without them they do not."""
        lot = self.env['stock.lot'].create({
            'name': '000TD-EP-777', 'product_id': self.product_device.id,
            'company_id': self.company.id,
        })
        result = self._autofill(**{SERIAL_KEY: '000TD-EP-777'})
        self.assertEqual(result['record'].get('lot_id'), lot.id)
        result = self._autofill(**{SERIAL_KEY: 'TD-EP-777'})
        self.assertNotIn('lot_id', result['record'])

    def test_ac16_digit_serial_leading_zeros_gs1(self):
        """AC-16 [US-05]: with the GS1 barcode nomenclature, stock_barcode turns a
        name search for a zero-padded digit serial into ``ilike`` on the unpadded
        digits. The lookup must still find only the exact serial number."""
        gs1 = self.env.ref('barcodes_gs1_nomenclature.default_gs1_nomenclature',
                           raise_if_not_found=False)
        if gs1:
            self.env.company.nomenclature_id = gs1
        exact = self.env['stock.lot'].create({
            'name': '000987654321', 'product_id': self.product_device.id,
            'company_id': self.company.id,
        })
        self.env['stock.lot'].create({
            'name': '9876543219', 'product_id': self.product_device2.id,
            'company_id': self.company.id,
        })
        result = self._autofill(**{SERIAL_KEY: '000987654321'})
        self.assertEqual(result['record'].get('lot_id'), exact.id)
        self.assertEqual(result['custom'], [])

    def test_ac16_serial_exact_case(self):
        """AC-16 [US-05]: the serial number must match exactly — another letter
        case finds nothing."""
        result = self._autofill(**{SERIAL_KEY: 'td-ep-sn-001'})
        self.assertNotIn('lot_id', result['record'])
        self.assertNotIn('product_id', result['record'])

    def test_ac16_controller_merges_values(self):
        """AC-16 [US-05]: the website controller writes the resolved values into
        the record of the form."""
        data = {'record': {'name': 'TD-EP form ticket'}, 'custom': ''}
        values = {
            EDRPOU_KEY: self.company_b.company_registry,
            SERIAL_KEY: self.lot_l.name,
        }
        with MockRequest(self.env):
            WebsiteFormEquipment()._td_autofill_helpdesk(values, data)
        self.assertEqual(data['record'].get('partner_id'), self.company_b.id)
        self.assertEqual(data['record'].get('lot_id'), self.lot_l.id)
        self.assertNotIn('td_equipment_id', data['record'])
        self.assertNotIn('td_serial_number_id', data['record'])

    # ── AC-17 ─────────────────────────────────────────────────────────

    def test_ac17_unknown_edrpou(self):
        """AC-17 [US-05]: S/N found, EDRPOU unknown → equipment only, no partner
        is created."""
        partner_count = self.env['res.partner'].search_count([])
        result = self._autofill(**{
            EDRPOU_KEY: self.unknown_edrpou,
            SERIAL_KEY: self.lot_l.name,
        })
        record = result['record']
        self.assertEqual(record.get('lot_id'), self.lot_l.id)
        self.assertEqual(record.get('product_id'), self.product_device.id)
        self.assertNotIn('partner_id', record)
        self.assertEqual(self.env['res.partner'].search_count([]), partner_count)

    # ── AC-18 ─────────────────────────────────────────────────────────

    def test_ac18_unknown_serial(self):
        """AC-18 [US-05]: EDRPOU found, S/N unknown → client only."""
        result = self._autofill(**{
            EDRPOU_KEY: self.company_b.company_registry,
            SERIAL_KEY: 'TD-EP-NO-SUCH-SN',
        })
        record = result['record']
        self.assertEqual(record.get('partner_id'), self.company_b.id)
        self.assertNotIn('lot_id', record)
        self.assertNotIn('product_id', record)

    # ── AC-19 ─────────────────────────────────────────────────────────

    def test_ac19_ambiguous_serial_owned_by_client(self):
        """AC-19 [US-05]: of two lots with the same S/N, the one owned by the
        client's company is chosen."""
        self.lot_dup1.sudo().td_owner_id = self.company_b
        result = self._autofill(**{
            EDRPOU_KEY: self.company_b.company_registry,
            SERIAL_KEY: 'TD-EP-DUP-1',
        })
        self.assertEqual(result['record'].get('lot_id'), self.lot_dup1.id)

    def test_ac19_ambiguous_serial_not_guessed(self):
        """AC-19 [US-05]: none of the lots relates to the client → no lot, and
        the candidates are listed for the engineer."""
        result = self._autofill(**{
            EDRPOU_KEY: self.company_b.company_registry,
            SERIAL_KEY: 'TD-EP-DUP-1',
        })
        self.assertNotIn('lot_id', result['record'])
        self.assertNotIn('product_id', result['record'])
        custom = '\n'.join(result['custom'])
        self.assertIn('%s — TD-EP-DUP-1' % self.product_device.display_name, custom)
        self.assertIn('%s — TD-EP-DUP-1' % self.product_device2.display_name, custom)

    # ── AC-20 ─────────────────────────────────────────────────────────

    def test_ac20_sanitize_protected_keys(self):
        """AC-20 [US-05]: the visitor cannot set the resolved fields himself."""
        values = {
            'name': 'TD-EP',
            'partner_id': '1', 'product_id': '2', 'lot_id': '3',
            'td_applicant_id': '4', 'td_applicant_edrpou': '12345678',
        }
        self.assertEqual(WebsiteFormEquipment._td_sanitize_values(values), {'name': 'TD-EP'})
