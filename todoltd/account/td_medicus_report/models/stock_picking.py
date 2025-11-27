# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'td.amount.to.words.mixin']


    def get_amount_in_words(self):
        """
        Returns the amount in words in Ukrainian
        """
        self.ensure_one()
        if hasattr(self, 'td_total_amount') and self.td_total_amount:
            amount = self.td_total_amount
        else:
            amount = sum(move.td_price_subtotal for move in self.move_ids_without_package if hasattr(move, 'td_price_subtotal'))
        
        if amount:
            return self._amount_to_words_ua(amount)
        return ''

    def td_get_report_data(self):
        """
        Preparation of data for the wholesale invoice report
        """
        self.ensure_one()
        
        company = self.company_id
        company_partner = company.partner_id
        partner = self.partner_id
        order = self.sale_id
        order_term_date = order.validity_date

        if order.payment_term_id:
            order_term_date = order_term_date + timedelta(days=order.payment_term_id.line_ids[0].nb_days)
            
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
            
            'agreement': {
                'number': order.td_agreement_id.number,
                'date': order.td_agreement_id.start_date,
            },
            
            'document_number': order.name.replace('S', ''),
            'document_date': self.scheduled_date,
            'payment_term': order_term_date,
            
            'lines': [],
            
            'amount_untaxed': self.td_total_without_tax,
            'amount_tax': self.td_total_tax,
            'amount_total': self.td_total_amount,
            'amount_in_words': self.get_amount_in_words(),
            'tax_guide_name': order.td_tax_guide_id.name,
            'currency_symbol': order.currency_id.symbol,
        }

        if order.partner_invoice_id != partner or order.partner_invoice_id.parent_id != partner:
            payment_partner = order.partner_invoice_id
            data['payment_partner'] = {
                'name': payment_partner.name,
                'street': payment_partner.street or '',
            }
        
        line_num = 0
        for move in self.move_ids_without_package:
            line_num += 1
            
            lots = []
            lot_id = move.product_id.stock_quant_ids.filtered(
                lambda q: q.lot_id.sale_order_ids == order
            ).lot_id
            
            line_data = {
                'sequence': line_num,
                'product_name': move.product_id.description_sale or move.product_id.name,
                'product_code': move.product_id.default_code or '',
                'product_serial_number': lot_id.name,
                'storage_conditions': self.location_id.mapped('td_condition_ids.name'),
                'quantity': move.product_uom_qty,
                'uom': move.product_uom.name,
                'price_unit': move.td_price_unit,
                'price_subtotal': move.td_price_subtotal,
            }
            data['lines'].append(line_data)
        
        return data
