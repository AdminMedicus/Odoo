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
        invoice = self.sale_id.invoice_ids.filtered(
            lambda i: i.state == 'posted'
        )[-1]
        if not invoice:
            raise ValueError("No posted invoice found for this picking.")
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
