# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'td.amount.to.words.mixin']


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
        warehouse_manager_id = company.td_warehouse_manager_id
        medical_manager_id = company.td_medical_warehouse_manager_id
        partner = order.partner_shipping_id or order.partner_id
        partner_name = (
                partner.parent_id.full_partner_name or partner.parent_id.name
            ) if partner.parent_id else (
                partner.full_partner_name or partner.name
            )
        delivery_partners = company_partner.child_ids.filtered(lambda p: p.type == 'delivery')
        
        contact_partners = partner.child_ids.filtered(
            lambda p: p.type == 'contact' and p.td_is_counterparty_physical_person
        )

        fisical_address_partner = delivery_partners[0] if delivery_partners else company_partner
        contact_partner = contact_partners[0] if contact_partners else partner
        
        data = {
            'is_picking': False,
            'is_invoice': True,
            'company': {
                'name': company_partner.full_partner_name,
                'registry': company.company_registry,
                'vat': company.vat,
                'street': company_partner.contact_address_complete,
                'logo': company.logo,
                'phone': company_partner.phone or '',
                'warehouse_manager': warehouse_manager_id.td_partner_short_name or warehouse_manager_id.name,
                'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.name,
                'responsible_manager': company.td_responsible_manager_id.td_partner_short_name or company.td_responsible_manager_id.name,
                'president': company.td_president_id.td_partner_short_name or company.td_president_id.name,
            },
            'company_partner': {
                'ref': company_partner.ref or '',
                'bank_account': company_partner.bank_ids[0].acc_number,
                'bank_name': company_partner.bank_ids[0].bank_name,
                'bank_bic': company_partner.bank_ids[0].bank_bic,
                'tax_position': company_partner.property_account_position_id.name,
            },
            'partner': {
                'name': partner_name,
                'registry': partner.company_registry or '',
                'street': partner.parent_id.contact_address_complete,
                'fisical_address': partner.contact_address_complete,
                'phone': partner.phone or '',
                'contact_person': contact_partner.name or '',
            },
            'payment_partner': False,
            'warehouse_address': '',
            'warehouse_city': '',
            
            'agreement': {
                'number': '',
                'date': '',
            },
            
            'document_number': self.name.split('/')[-1],
            # 'document_number': order.name.replace('S', ''),
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

        if agreement := self.td_agreement_id:
            if not agreement.start_date:
                raise UserError(f'У договорі "{agreement.name}" не вказана дата початку.')
            data['agreement']['number'] = agreement.agreement_number
            data['agreement']['date'] = agreement.start_date.strftime('%d.%m.%Y')

        if order.partner_invoice_id and order.partner_invoice_id != partner:
            partner_root = partner.parent_id or partner
            invoice_root = order.partner_invoice_id.parent_id or order.partner_invoice_id
            
            if invoice_root != partner_root:
                payment_partner = order.partner_invoice_id
                data['payment_partner'] = {
                    'registry': payment_partner.company_registry or '',
                    'name': payment_partner.full_partner_name or payment_partner.name,
                    'street': payment_partner.contact_address_complete or '',
                }
        
        line_num = 0
        for line in self.invoice_line_ids:
            if not line.product_id:
                continue

            location = order.picking_ids.filtered(
                lambda p: line.td_order_line_id in p.move_ids_without_package.sale_line_id
            ).location_id
            move_line_ids = line.sale_line_ids.move_ids.filtered(
                lambda m: m.picking_id.picking_type_code == 'outgoing'
            ).mapped('move_line_ids')

            data['warehouse_address'] = fisical_address_partner.contact_address_complete

            if move_line_ids:
                for ml in move_line_ids:
                    line_num += 1
                    line_data = {
                        'sequence': line_num,
                        'product_name': line.product_id.description_sale,
                        'product_code': line.product_id.default_code or '',
                        'product_serial_numbers': [ml.lot_id.name] if ml.lot_id else [],
                        'product_catalog_number': line.product_id.default_code or '',
                        'product_manufacturer': line.product_id.td_manufacturer_directory_res_id.name or '',
                        'storage_conditions': location.mapped('td_condition_ids.name'),
                        'quantity': ml.quantity,
                        'uom': line.product_uom_id.name,
                        'expiration_dates': [ml.expiration_date.strftime('%d.%m.%Y')] if ml.expiration_date else [],
                        'price_untaxed': line.td_untaxed_price_unit,
                        'price_subtotal': line.td_untaxed_price_unit * ml.quantity,
                    }
                    data['lines'].append(line_data)
            else:
                line_num += 1
                line_data = {
                    'sequence': line_num,
                    'product_name': line.product_id.description_sale,
                    'product_code': line.product_id.default_code or '',
                    'product_serial_numbers': [],
                    'product_catalog_number': line.product_id.default_code or '',
                    'product_manufacturer': line.product_id.td_manufacturer_directory_res_id.name or '',
                    'storage_conditions': location.mapped('td_condition_ids.name'),
                    'quantity': line.quantity,
                    'uom': line.product_uom_id.name,
                    'expiration_dates': [],
                    'price_untaxed': line.td_untaxed_price_unit,
                    'price_subtotal': line.price_subtotal,
                }
                data['lines'].append(line_data)

        return data
