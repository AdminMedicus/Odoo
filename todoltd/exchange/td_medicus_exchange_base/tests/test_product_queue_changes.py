from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestProductQueueChanges(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({
            'name': 'BAS queue regression product',
        })
        cls.method = cls.env.ref('td_medicus_exchange_base.product_odoo_1c')

    def _queue(self):
        return self.env['ata.exchange.queue'].sudo().search([
            ('ref_object', '=', f'product.product,{self.product.id}'),
            ('method', '=', self.method.id),
        ])

    def _clear_queue(self):
        self._queue().unlink()

    def test_template_technical_write_does_not_queue_product(self):
        self._clear_queue()
        self.product.product_tmpl_id.write({'description': 'Not used by BAS'})
        self.assertFalse(self._queue())

    def test_product_technical_write_does_not_queue_product(self):
        self._clear_queue()
        self.product.write({'description': 'Stock-related metadata'})
        self.assertFalse(self._queue())

    def test_same_barcode_does_not_queue_product(self):
        self._clear_queue()
        self.product.write({'barcode': self.product.barcode})
        self.assertFalse(self._queue())

    def test_template_name_change_queues_product(self):
        self._clear_queue()
        self.product.product_tmpl_id.write({'name': 'Changed BAS product name'})
        self.assertEqual(len(self._queue()), 1)

    def test_product_barcode_change_queues_product(self):
        self._clear_queue()
        self.product.write({'barcode': 'BAS-QUEUE-REGRESSION'})
        self.assertEqual(len(self._queue()), 1)
