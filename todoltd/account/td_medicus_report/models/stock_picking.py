# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _amount_to_words_ua(self, amount):
        """Конвертує число в текст українською мовою"""
        ones = ['', 'одна', 'дві', 'три', 'чотири', 'п\'ять', 'шість', 'сім', 'вісім', 'дев\'ять']
        tens = ['', 'десять', 'двадцять', 'тридцять', 'сорок', 'п\'ятдесят', 
                'шістдесят', 'сімдесят', 'вісімдесят', 'дев\'яносто']
        teens = ['десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять',
                'п\'ятнадцять', 'шістнадцять', 'сімнадцять', 'вісімнадцять', 'дев\'ятнадцять']
        hundreds = ['', 'сто', 'двісті', 'триста', 'чотириста', 'п\'ятсот',
                    'шістсот', 'сімсот', 'вісімсот', 'дев\'ятсот']
        thousands = ['тисяча', 'тисячі', 'тисяч']
        
        def num_to_words(n):
            if n == 0:
                return 'нуль'
            
            if n < 10:
                return ones[n]
            elif n < 20:
                return teens[n - 10]
            elif n < 100:
                return tens[n // 10] + (' ' + ones[n % 10] if n % 10 != 0 else '')
            elif n < 1000:
                return hundreds[n // 100] + (' ' + num_to_words(n % 100) if n % 100 != 0 else '')
            elif n < 1000000:
                thousands_digit = n // 1000
                remainder = n % 1000
                
                # Визначаємо форму слова "тисяча"
                if thousands_digit % 10 == 1 and thousands_digit % 100 != 11:
                    thousand_word = thousands[0]
                elif thousands_digit % 10 in [2, 3, 4] and thousands_digit % 100 not in [12, 13, 14]:
                    thousand_word = thousands[1]
                else:
                    thousand_word = thousands[2]
                
                result = num_to_words(thousands_digit) + ' ' + thousand_word
                if remainder != 0:
                    result += ' ' + num_to_words(remainder)
                return result
            else:
                return str(n)
        
        # Розділяємо на цілу та дробову частини
        whole_part = int(amount)
        decimal_part = int(round((amount - whole_part) * 100))
        
        result = num_to_words(whole_part).capitalize()
        
        # Додаємо гривні
        if whole_part % 10 == 1 and whole_part % 100 != 11:
            result += ' гривня'
        elif whole_part % 10 in [2, 3, 4] and whole_part % 100 not in [12, 13, 14]:
            result += ' гривні'
        else:
            result += ' гривень'
        
        # Додаємо копійки
        result += f' {decimal_part:02d} копійок'
        
        return result

    def get_amount_in_words(self):
        """Повертає суму в словах українською"""
        self.ensure_one()
        # Використовуємо td_total_amount якщо є, інакше рахуємо з moves
        if hasattr(self, 'td_total_amount') and self.td_total_amount:
            amount = self.td_total_amount
        else:
            amount = sum(move.td_price_subtotal for move in self.move_ids_without_package if hasattr(move, 'td_price_subtotal'))
        
        if amount:
            return self._amount_to_words_ua(amount)
        return ''

    def get_invoice_related(self):
        """Повертає пов'язаний інвойс якщо є"""
        self.ensure_one()
        if self.sale_id:
            invoice = self.env['account.move'].search([
                ('invoice_origin', '=', self.sale_id.name),
                ('move_type', '=', 'out_invoice')
            ], limit=1)
            return invoice
        return self.env['account.move']

    def td_get_report_data(self):
        """
        Підготовка даних для звіту оптової накладної
        """
        self.ensure_one()
        
        company = self.company_id
        company_partner = company.partner_id
        partner = self.partner_id
        order = self.sale_id
        order_term_date = order.validity_date + timedelta(days=order.payment_term_id.line_ids[0].nb_days)
        
        # Базові дані
        data = {
            'is_picking': True,
            'is_invoice': False,
            'company': {
                'name': company.name,
                'registry': company.company_registry or '',
                'vat': company.vat or '',
                'street': company.street or '',
                'logo': company.logo,
                'warehouse_manager': company.td_warehouse_manager_id.name,
                'medical_warehouse_manager': company.td_medical_warehouse_manager_id.name,
            },
            'company_partner': {
                'ref': company_partner.ref or '',
                'bank_account': company_partner.bank_ids[0].acc_number,
                'bank_name': company_partner.bank_ids[0].bank_name,
                'bank_bic': company_partner.bank_ids[0].bank_bic,
                'license_issued_by': company_partner.td_license_issued_by,
                'license_number': company_partner.td_license_number,
                'license_date': company_partner.td_license_date,
                'tax_position': company_partner.property_account_position_id.name,
            },
            'partner': {
                'name': partner.name,
                'street': partner.street or '',
            },
            'warehouse_address': self.warehouse_address_id.street,
            'warehouse_city': self.picking_type_id.warehouse_id.partner_id.city,
            
            # Договір
            'agreement': {
                'number': order.td_agreement_id.number,
                'date': order.td_agreement_id.start_date,
            },
            
            # Дати та номери
            'document_number': order.name.replace('S', ''),
            'document_date': self.scheduled_date,
            'payment_term': order_term_date,
            
            # Товарні позиції
            'lines': [],
            
            # Суми
            'amount_untaxed': self.td_total_without_tax,
            'amount_tax': self.td_total_tax,
            'amount_total': self.td_total_amount,
            'amount_in_words': self.get_amount_in_words(),
            'tax_guide_name': order.td_tax_guide_id.name,
            'currency_symbol': order.currency_id.symbol,
        }
        
        # Формування товарних позицій
        line_num = 0
        for move in self.move_ids_without_package:
            line_num += 1
            
            # Серії та терміни придатності
            lots = []
            lot_id = move.product_id.stock_quant_ids.filtered(
                lambda q: q.lot_id.sale_order_ids == order
            ).lot_id
            
            line_data = {
                'sequence': line_num,
                'product_name': move.product_id.name,
                'product_code': move.product_id.default_code or '',
                'product_serial_number': lot_id,
                'storage_conditions': move.product_id.td_product_conditions,
                'quantity': move.product_uom_qty,
                'uom': move.product_uom.name,
                'price_unit': move.td_price_unit,
                'price_subtotal': move.td_price_subtotal,
            }
            data['lines'].append(line_data)
        
        return data
