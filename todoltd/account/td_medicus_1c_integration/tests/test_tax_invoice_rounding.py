from odoo.tests import common, tagged
from odoo.tools import float_compare


@tagged('post_install', '-at_install')
class TestTaxInvoiceRounding(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
    
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner'})
        cls.product = cls.env['product.product'].create({
            'lst_price': 100.445,
            'name': 'Test Product',
            'type': 'consu',
        })


        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.partner.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Line 1',
                'price_unit': 100.445,
                'product_id': cls.product.id,
                'quantity': 3,
            })],
        })
        cls.invoice.action_post()

        cls.payment_line = cls.env['account.move.line'].create({
            'account_id': cls.invoice.line_ids[0].account_id.id,
            'credit': 301.34,
            'move_id': cls.invoice.id,
            'name': 'Test Payment',
            'partner_id': cls.partner.id,
        })

    def test_recalculation_rounding_remainder(self):
        """Перевірка розподілу залишку копійки на останній рядок"""
        

        tax_invoice = self.env['td.tax.invoice'].create({
            'invoice_id': self.invoice.id,
            'invoice_type': 'invoice',
            'partner_id': self.partner.id,
            'payment_id': self.payment_line.id,
            'td_invoice_line_ids': [
                (0, 0, {
                    'price_with_out_vat': 100.445,
                    'product_id': self.product.id,
                    'quantity': 0,
                    'sum_price_with_out_vat': 150.67,
                }),
                (0, 0, {
                    'price_with_out_vat': 100.445,
                    'product_id': self.product.id,
                    'quantity': 0,
                    'sum_price_with_out_vat': 150.67,
                })
            ],
        })


        tax_invoice.recalculation_of_the_quantity_of_lines()


        total_calculated_amount = sum(
            line.quantity * line.price_with_out_vat 
            for line in tax_invoice.td_invoice_line_ids
        )
        

        precision = self.company.currency_id.rounding
        comparison = float_compare(total_calculated_amount, 301.34, precision_rounding=precision)
        
        self.assertEqual(comparison, 0, f"Сума {total_calculated_amount} не збігається з очікуваною 301.34")


        for line in tax_invoice.td_invoice_line_ids:
            self.assertTrue(line.quantity > 0, "Кількість не була розрахована")
