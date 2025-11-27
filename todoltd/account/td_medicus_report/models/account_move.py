# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'td.amount.to.words.mixin']

    # def _amount_to_words_ua(self, amount):
    #     """
    #     Converts a number into Ukrainian words
    #     """
    #     ones = ['', 'одна', 'дві', 'три', 'чотири', 'п\'ять', 'шість', 'сім', 'вісім', 'дев\'ять']
    #     tens = ['', 'десять', 'двадцять', 'тридцять', 'сорок', 'п\'ятдесят', 
    #             'шістдесят', 'сімдесят', 'вісімдесят', 'дев\'яносто']
    #     teens = ['десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять',
    #             'п\'ятнадцять', 'шістнадцять', 'сімнадцять', 'вісімнадцять', 'дев\'ятнадцять']
    #     hundreds = ['', 'сто', 'двісті', 'триста', 'чотириста', 'п\'ятсот',
    #                 'шістсот', 'сімсот', 'вісімсот', 'дев\'ятсот']
    #     thousands = ['тисяча', 'тисячі', 'тисяч']
        
    #     def num_to_words(n):
    #         if n == 0:
    #             return 'нуль'
            
    #         if n < 10:
    #             return ones[n]
    #         elif n < 20:
    #             return teens[n - 10]
    #         elif n < 100:
    #             return tens[n // 10] + (' ' + ones[n % 10] if n % 10 != 0 else '')
    #         elif n < 1000:
    #             return hundreds[n // 100] + (' ' + num_to_words(n % 100) if n % 100 != 0 else '')
    #         elif n < 1000000:
    #             thousands_digit = n // 1000
    #             remainder = n % 1000
                
    #             if thousands_digit % 10 == 1 and thousands_digit % 100 != 11:
    #                 thousand_word = thousands[0]
    #             elif thousands_digit % 10 in [2, 3, 4] and thousands_digit % 100 not in [12, 13, 14]:
    #                 thousand_word = thousands[1]
    #             else:
    #                 thousand_word = thousands[2]
                
    #             result = num_to_words(thousands_digit) + ' ' + thousand_word
    #             if remainder != 0:
    #                 result += ' ' + num_to_words(remainder)
    #             return result
    #         else:
    #             return str(n)
        
    #     whole_part = int(amount)
    #     decimal_part = int(round((amount - whole_part) * 100))
        
    #     result = num_to_words(whole_part).capitalize()
        
    #     if whole_part % 10 == 1 and whole_part % 100 != 11:
    #         result += ' гривня'
    #     elif whole_part % 10 in [2, 3, 4] and whole_part % 100 not in [12, 13, 14]:
    #         result += ' гривні'
    #     else:
    #         result += ' гривень'
        
    #     result += f' {decimal_part:02d} копійок'
        
    #     return result

    def get_amount_in_words(self):
        """
        Returns the amount in words in Ukrainian
        """
        self.ensure_one()
        if self.amount_total:
            return self._amount_to_words_ua(self.amount_total)
        return ''

    def td_get_report_data(self):
        """
        Preparation of data for the wholesale invoice report
        """
        self.ensure_one()
        
        order = self.td_order_id
        company = self.company_id
        company_partner = company.partner_id
        partner = order.partner_id
        
        data = {
            'is_picking': False,
            'is_invoice': True,
            'company': {
                'name': company.name,
                'registry': company.company_registry,
                'vat': company.vat,
                'street': company.street,
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
                'street': partner.street,
            },
            'payment_partner': False,
            'warehouse_address': '',
            'warehouse_city': '',
            
            'agreement': {
                'number': self.td_agreement_id.number,
                'date': self.td_agreement_id.start_date,
            },
            
            'document_number': order.name.replace('S', ''),
            'document_date': self.invoice_date.strftime('%d.%m.%Y'),
            'payment_term': self.invoice_date_due.strftime('%d.%m.%Y'),
            
            'lines': [],
            
            'amount_untaxed': self.amount_untaxed,
            'amount_tax': self.amount_tax,
            'amount_total': self.amount_total,
            'amount_in_words': self.get_amount_in_words(),
            'tax_guide_name': self.td_tax_guide_id.name,
            'currency_symbol': self.currency_id.symbol,
        }

        if order.partner_invoice_id != partner or (
            order.partner_invoice_id.parent_id and order.partner_invoice_id.parent_id != partner
        ):
            payment_partner = order.partner_invoice_id
            data['payment_partner'] = {
                'name': payment_partner.name,
                'street': payment_partner.street or '',
            }
        
        line_num = 0
        for line in self.invoice_line_ids:
            if not line.product_id:
                continue
            line_num += 1
            lot_id = line.product_id.stock_quant_ids.filtered(
                lambda q: q.lot_id.sale_order_ids == order
            ).lot_id
            location = order.picking_ids.filtered(
                lambda p: line.td_order_line_id in p.move_ids_without_package.sale_line_id
            ).location_id
            
            line_data = {
                'sequence': line_num,
                'product_name': line.product_id.name,
                'product_code': line.product_id.default_code or '',
                'product_serial_number': lot_id.name,
                'storage_conditions': location.mapped('td_condition_ids.name'),
                'quantity': line.quantity,
                'uom': line.product_uom_id.name,
                'price_unit': line.price_unit,
                'price_subtotal': line.price_subtotal,
            }
            data['warehouse_address'] = line.sale_line_ids[0].warehouse_id.partner_id.street or ''
            data['lines'].append(line_data)
        
        return data
