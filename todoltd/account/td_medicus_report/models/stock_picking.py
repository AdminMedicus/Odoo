# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import models
from odoo.tools.misc import format_date


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'td.amount.to.words.mixin']


    # def button_validate(self):
    #     res = super().button_validate()
        
    #     for picking in self:
    #         if picking.picking_type_code == 'outgoing' and (order := picking.sale_id):
    #             wizard = self.env['sale.advance.payment.inv'].with_context(
    #                 active_ids=[order.id],
    #                 active_model='sale.order',
    #                 active_id=order.id,
    #             ).create({
    #                 'td_advance_payment_method': 'delivered',
    #             })
                
    #             wizard.create_invoices()
                
    #             invoice = order.invoice_ids.filtered(
    #                 lambda inv: inv.state == 'draft'
    #             ).sorted('id', reverse=True)[:1]
                
    #             if invoice:
    #                 invoice.invoice_date = datetime.now().date()
    #                 invoice.action_post()
        
    #     return res

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
        
        invoices = self.sale_id.invoice_ids.filtered(
            lambda i: i.state == 'posted'
        )
        
        if not invoices:
            from odoo.exceptions import UserError
            raise UserError(
                f"Не можна надрукувати Оптову накладну:\n\n"
                f"Для замовлення {self.sale_id.name} ще не створено та не підтверджено інвойс.\n"
                f"Спочатку потрібно створити та підтвердити інвойс."
            )
        
        invoice = invoices[-1]
        data = invoice.td_get_report_data()
        return data

    def td_get_report_lenses_data(self):
        """
        Preparation of data for the lenses report
        """
        self.ensure_one()
        order = self.sale_id
        delivery_datetime = order.commitment_date or self.scheduled_date
        partner = self.partner_id
        current_user = self.env.user.partner_id
        
        data = {
            'name': order.name.replace('S', ''),
            'date': order.date_order.date().strftime('%d.%m.%Y'),
            'warehouse_name': self.location_id.warehouse_id.name,
            'partner_name': partner.full_partner_name or partner.name,
            'employee_name': current_user.full_partner_name or current_user.name,
            'document': dict(self._fields['implementation_document']._description_selection(self.env)).get(self.implementation_document, ''),
            'delivery_address': order.partner_shipping_id.street,
            'delivery_method': partner.property_delivery_carrier_id.name,
            'recipient_name': order.partner_shipping_id.full_partner_name,
            'recipient_phone': order.partner_shipping_id.phone,
            'delivery_time': delivery_datetime.time().strftime('%H:%M'),
            'delivery_date': delivery_datetime.date().strftime('%d.%m.%Y'),
            'lines': [],
            'amount_untaxed': self.td_total_without_tax,
            'amount_tax': self.td_total_tax,
            'amount_total': self.td_total_amount,
            'tax_guide_name': order.td_tax_guide_id.name,
        }

        line_num = 0
        for move in self.move_ids_without_package:
            line_num += 1
            
            line_data = {
                'sequence': line_num,
                'product_name': move.product_id.description_sale or move.product_id.name,
                'product_manufacturer': move.product_id.td_manufacturer_directory_res_id.name,
                'quantity': move.product_uom_qty,
                'price_unit': move.td_price_unit,
                'price_subtotal': move.td_price_subtotal,
                # 'quant': 
            }
            data['lines'].append(line_data)
        
        return data

    def td_get_report_waybill_data(self):
        """
        Preparation of data for the waybill report
        """
        self.ensure_one()
        order = self.sale_id
        company = self.company_id
        partner = self.partner_id

        data = {
            'waybill_number': self.name.split('/')[-1],
            'waybill_date': format_date(self.env, self.date_done, date_format='dd MMMM yyyy p.'),
            'buyer': order.partner_invoice_id.full_partner_name or order.partner_invoice_id.name,
            'shipper': company.partner_id.full_partner_name,
            # 'shipper': 'Товариство з обмеженою відповідальністю "Медична компанія Медікус"',
            'consignee': partner.full_partner_name or partner.name,
            'delivery_address': partner.contact_address_complete,
            'loading_point': self.warehouse_address_id.contact_address_complete or self.warehouse_address_id.name,
            'warehouse_manager': company.td_warehouse_manager_id.name,
            'medical_warehouse_manager': company.td_medical_warehouse_manager_id.name,
            'total_amount': self._amount_to_words_ua(self.td_total_amount),
            'tax_amount': self._amount_to_words_ua(self.td_total_tax),
            'total': self.td_total_amount,
            'lines': [],
        }

        line_num = 0
        for move in self.move_ids_without_package:
            line_num += 1
            
            line_data = {
                'sequence': line_num,
                'product_name': move.product_id.description_sale or move.product_id.name,
                'uom': move.product_uom.name,
                'quantity': move.product_uom_qty,
                'price_unit': move.td_price_unit,
                'price_subtotal': move.td_price_total,
                # 'packaging_type': move.package_level_id.name or '',
                'documents_with_cargo': self.origin or '',
                # 'gross_weight': move.td_gross_weight or '',
            }
            data['lines'].append(line_data)
        
        return data

    def td_get_report_custody_act_data(self):
        """
        Preparation of data for the custody act report
        """
        self.ensure_one()
        order = self.sale_id
        company = self.company_id
        company_partner = company.partner_id
        warehouse_manager_id = company.td_warehouse_manager_id.work_contact_id
        medical_manager_id = company.td_medical_warehouse_manager_id.work_contact_id
        client_partner = self.td_parent_partner_id
        shipper_partner = self.partner_id
        
        data = {
            'company': {
                'name': company_partner.full_partner_name,
                'registry': company.company_registry,
                'vat': company.vat,
                'street': company_partner.contact_address_complete,
                'logo': company.logo,
                'ref': company_partner.ref or '',
                'bank_account': company_partner.bank_ids[0].acc_number,
                'bank_name': company_partner.bank_ids[0].bank_name,
                'bank_bic': company_partner.bank_ids[0].bank_bic,
                'license_issued_by': company_partner.td_license_issued_by,
                'license_number': company_partner.td_license_number,
                'license_date': company_partner.td_license_date,
                'tax_position': company_partner.property_account_position_id.name,
                'warehouse_manager': warehouse_manager_id.full_partner_name,
                'medical_warehouse_manager': medical_manager_id.full_partner_name,
                # 'warehouse_manager': warehouse_manager_id.td_short_name or warehouse_manager_id.full_partner_name,
                # 'medical_warehouse_manager': medical_manager_id.td_short_name or medical_manager_id.full_partner_name,
                'warehouse_address': self.warehouse_address_id.contact_address_complete or self.warehouse_address_id.name
            },
            'partner': {
                'name': client_partner.parent_id.full_partner_name or client_partner.full_partner_name,
                'registry': client_partner.company_registry,
                'street': client_partner.parent_id.contact_address_complete,
                'fisical_address': shipper_partner.contact_address_complete,
            },
            'lines': [],
            'act_number': self.name.split('/')[-1],
            'act_date': self.date_done.strftime('%d.%m.%Y'),
            'agreement_number': order.td_agreement_id.agreement_number or '',
            'agreement_date': order.td_agreement_id.start_date.strftime('%d.%m.%Y'),
            'transfer_title': 'Акт передачі майна на відповідальне зберігання № ',
            'return_title': 'Акт повернення майна з відповідального зберігання № ',
            'transfer_subtitle': 'Депонент передав, а виконавець прийняв на відповідальне зберігання наступне майно:',
            'return_subtitle': 'Депонент прийняв, а виконавець повернув з відповідального зберігання наступне майно:',
            'amount_total': self.td_total_amount,
            'amount_in_words': self.get_amount_in_words(),
        }

        line_num = 0
        for line in self.move_ids_without_package:
            if not line.product_id:
                continue
            line_num += 1
            location = self.location_id
            move_line_ids = line.mapped('move_line_ids')
            
            line_data = {
                'sequence': line_num,
                'product_name': line.product_id.description_sale,
                'product_code': line.product_id.default_code or '',
                'product_serial_numbers': [
                    l.name for l in move_line_ids.mapped('lot_id')]
                    if move_line_ids else [],
                'product_catalog_number': line.product_id.default_code or '',
                'product_manufacturer': line.product_id.td_manufacturer_directory_res_id.name or '',
                'storage_conditions': location.mapped('td_condition_ids.name'),
                'quantity': line.quantity,
                'uom': line.product_uom.name,
                'expiration_dates': [
                    d.strftime('%d.%m.%Y') for d in move_line_ids.mapped('expiration_date')]
                    if move_line_ids else [],
                'price_unit': line.td_price_unit,
                'price_subtotal': line.td_price_subtotal,
            }
            data['lines'].append(line_data)
        
        return data
