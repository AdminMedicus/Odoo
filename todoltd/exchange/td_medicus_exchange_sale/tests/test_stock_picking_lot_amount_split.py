from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestStockPickingLotAmountSplit(TransactionCase):

    def _split(self, line_data):
        return self.env[
            'stock.picking'
        ]._ata_exchange_split_line_by_lots(line_data)

    def test_totals_are_allocated_by_lot_quantity(self):
        source = {
            'id': 31,
            'quantity': 60.0,
            'price_unit_untaxed': 269.96,
            'price_unit': 269.96,
            'price_subtotal': 16197.60,
            'price_total': 17331.432,
            'lots_data': [
                {'lot': {'id': 'LOT-15'}, 'quantity': 15.0},
                {'lot': {'id': 'LOT-45'}, 'quantity': 45.0},
            ],
        }

        lines = self._split(source)

        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]['quantity'], 15.0)
        self.assertEqual(lines[1]['quantity'], 45.0)
        self.assertEqual(len(lines[0]['lots_data']), 1)
        self.assertEqual(len(lines[1]['lots_data']), 1)
        self.assertAlmostEqual(lines[0]['price_subtotal'], 4049.40)
        self.assertAlmostEqual(lines[1]['price_subtotal'], 12148.20)
        self.assertAlmostEqual(lines[0]['price_total'], 4332.858)
        self.assertAlmostEqual(lines[1]['price_total'], 12998.574)
        self.assertAlmostEqual(
            sum(line['price_subtotal'] for line in lines),
            source['price_subtotal'],
        )
        self.assertAlmostEqual(
            sum(line['price_total'] for line in lines),
            source['price_total'],
        )
        self.assertTrue(all(
            line['price_unit'] == source['price_unit']
            for line in lines
        ))

    def test_single_lot_keeps_original_line(self):
        source = {
            'id': 31,
            'quantity': 60.0,
            'price_subtotal': 16197.60,
            'price_total': 17331.432,
            'lots_data': [
                {'lot': {'id': 'LOT-60'}, 'quantity': 60.0},
            ],
        }

        self.assertEqual(self._split(source), [source])

    def test_last_lot_receives_allocation_remainder(self):
        source = {
            'id': 31,
            'quantity': 3.0,
            'price_subtotal': 0.01,
            'price_total': 0.01,
            'lots_data': [
                {'lot': {'id': 'LOT-1'}, 'quantity': 1.0},
                {'lot': {'id': 'LOT-2'}, 'quantity': 1.0},
                {'lot': {'id': 'LOT-3'}, 'quantity': 1.0},
            ],
        }

        lines = self._split(source)

        self.assertAlmostEqual(
            sum(line['price_subtotal'] for line in lines),
            source['price_subtotal'],
        )
        self.assertAlmostEqual(
            sum(line['price_total'] for line in lines),
            source['price_total'],
        )
