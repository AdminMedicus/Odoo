from odoo import models


class TdAmountToWordsMixin(models.AbstractModel):
    _name = 'td.amount.to.words.mixin'
    _description = 'Mixin to convert amount to words in Ukrainian'

    def _amount_to_words_ua(self, amount):
        """
        Converts a number into Ukrainian words
        """
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
        
        whole_part = int(amount)
        decimal_part = int(round((amount - whole_part) * 100))
        
        result = num_to_words(whole_part).capitalize()
        
        if whole_part % 10 == 1 and whole_part % 100 != 11:
            result += ' гривня'
        elif whole_part % 10 in [2, 3, 4] and whole_part % 100 not in [12, 13, 14]:
            result += ' гривні'
        else:
            result += ' гривень'
        
        result += f' {decimal_part:02d} копійок'
        
        return result
