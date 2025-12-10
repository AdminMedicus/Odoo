# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'td.amount.to.words.mixin']

    td_invoice_date = fields.Date(
        string="Invoice Date",
        help="Date of the invoice related to this delivery order",
    )
    td_custody_act_date = fields.Date(
        string="Custody Act Date",
        help="Date of the custody act related to this delivery order",
    )
    td_order_implementation_document = fields.Selection(
        related="sale_id.implementation_document",
        store=True,
    )
    td_show_create_invoice_button = fields.Boolean(
        string="Show Create Invoice Button",
        compute='_compute_td_show_create_invoice_button',
    )
    td_show_create_custody_act_button = fields.Boolean(
        string="Show Create Custody Act Button",
        compute='_compute_td_show_create_custody_act_button',
    )
    td_invoice_for_pick_id = fields.Many2one(
        comodel_name='account.move',
        string="Invoice for Picking",
        help="The invoice created from this picking",
    )


    def _compute_td_show_create_invoice_button(self):
        for picking in self:
            if picking.td_order_implementation_document == 'exp_inv':
                pickings = picking.sale_id.picking_ids.filtered(
                    lambda p: p.picking_type_code in ['internal', 'outgoing']
                )
                all_pickings_done = all(p.state == 'done' for p in pickings)
                picking.td_show_create_invoice_button = (
                    picking.picking_type_code in ['internal', 'outgoing'] and 
                    all_pickings_done and 
                    not picking.sale_id.td_invoice_from_delivery
                )
            elif picking.td_order_implementation_document == 'act_res_st':
                picking.td_show_create_invoice_button = (
                    picking.picking_type_code == 'incoming' and
                    picking.state == 'done' and
                    bool(picking.return_id) and
                    not picking.sale_id.td_invoice_from_delivery
                )
            else:
                picking.td_show_create_invoice_button = False

    def _compute_td_show_create_custody_act_button(self):
        for picking in self:
            picking.td_show_create_custody_act_button = (
                picking.state == 'done' and
                picking.picking_type_code in ['outgoing', 'incoming'] and
                picking.td_order_implementation_document == 'act_res_st'
            )

    def td_create_invoice(self):
        """
        Create invoice from delivery order and print it
        """
        self.ensure_one()
        sale_order = self.sale_id
        if not sale_order:
            return
        
        wizard = self.env['sale.advance.payment.inv'].with_context(
            active_ids=[sale_order.id],
            active_model='sale.order',
            active_id=sale_order.id,
        ).create({
            'td_advance_payment_method': 'delivered',
        })
        
        invoice_action = wizard.create_invoices()
        
        invoice = sale_order.invoice_ids.filtered(
            lambda inv: inv.id == invoice_action['res_id']
        )
        
        if invoice:
            invoice.invoice_date = self.td_invoice_date or datetime.now().date()
            invoice.action_post()
            sale_order.td_invoice_from_delivery = True
            self.td_invoice_for_pick_id = invoice.id
            
            return self.env.ref('td_medicus_report.action_report_wholesale_invoice_invoice').report_action(invoice)

    def td_create_custody_act(self):
        """
        Create custody act from delivery order and print it
        """
        self.ensure_one()
        if not self.td_custody_act_date:
            self.td_custody_act_date = datetime.now().date()

        if self.picking_type_code == 'outgoing':
            return self.env.ref('td_medicus_report.action_report_custody_transfer_act').report_action(self)
        elif self.picking_type_code == 'incoming' and self.return_id:
            return self.env.ref('td_medicus_report.action_report_custody_return_act').report_action(self)

    @api.onchange('td_invoice_date', 'td_custody_act_date')
    def _onchange_td_dates(self):
        """
        Synchronize td_invoice_date across all transfers in the chain
        """
        if self.td_invoice_date or self.td_custody_act_date:
            self._sync_invoice_date_in_chain(
                invoice_date=self.td_invoice_date,
                custody_date=self.td_custody_act_date
            )

    def _sync_invoice_date_in_chain(self, invoice_date=None, custody_date=None):
        """
        Synchronize invoice date across all related transfers in the chain
        """
        self.ensure_one()
        if not self.sale_id:
            return
        
        all_pickings = self.sale_id.picking_ids.filtered(
            lambda p: p.state not in ['cancel'] and p.id != self.id
        )
        
        if all_pickings:
            data = {}
            if invoice_date:
                data['td_invoice_date'] = invoice_date
            if custody_date:
                data['td_custody_act_date'] = custody_date
            all_pickings.write(data)

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
        shipping_contacts = order.partner_shipping_id.child_ids.filtered(
            lambda p: p.type == 'contact'
        )
        shipping_partner = shipping_contacts[0] if shipping_contacts else order.partner_shipping_id
        
        data = {
            'name': order.name.replace('S', ''),
            'date': order.date_order.date().strftime('%d.%m.%Y'),
            'warehouse_name': self.location_id.warehouse_id.name,
            'partner_name': partner.full_partner_name or partner.name,
            'employee_name': current_user.full_partner_name or current_user.name,
            'document': dict(self._fields['implementation_document']._description_selection(self.env)).get(self.implementation_document, ''),
            'delivery_address': order.partner_shipping_id.street,
            'delivery_method': partner.property_delivery_carrier_id.name,
            # 'recipient_name': order.partner_shipping_id.full_partner_name,
            # 'recipient_phone': order.partner_shipping_id.phone,
            'recipient_name': shipping_partner.full_partner_name or shipping_partner.name,
            'recipient_phone': shipping_partner.phone,
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
                # 'stock_inventory': move.product_id.property_stock_inventory.name or '',
                'stock_inventory': move.move_line_ids.mapped('location_id.complete_name'),
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
        warehouse_manager_id = company.td_warehouse_manager_id
        medical_manager_id = company.td_medical_warehouse_manager_id

        data = {
            'waybill_number': self.name.split('/')[-1],
            'waybill_date': format_date(self.env, self.date_done, date_format='dd MMMM yyyy p.'),
            'buyer': order.partner_invoice_id.full_partner_name or order.partner_invoice_id.name,
            'shipper': company.partner_id.full_partner_name,
            'consignee': partner.full_partner_name or partner.name,
            'delivery_address': partner.contact_address_complete,
            'loading_point': self.warehouse_address_id.contact_address_complete or self.warehouse_address_id.name,
            'warehouse_manager': warehouse_manager_id.td_partner_short_name or warehouse_manager_id.name,
            'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.name,
            'accompanying_document': f"Фарм РН. № {self.td_invoice_for_pick_id.name.split('/')[-1]} від ",
            'accompanying_document_date': self.td_invoice_for_pick_id.invoice_date.strftime('%d.%m.%Y'),
            'accompanying_document_full_date': format_date(self.env, self.td_invoice_for_pick_id.invoice_date, date_format='dd MMMM yyyy p.'),
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
                'documents_with_cargo': self.origin or '',
            }
            data['lines'].append(line_data)
        
        return data

    def td_get_report_custody_act_data(self):
        """
        Preparation of data for the custody act report
        """
        self.ensure_one()

        order = self.sale_id

        if not order.td_agreement_id:
            raise UserError(f"У замовленні {order.name} не вказано договір.")

        if not order.td_agreement_id.start_date:
            raise UserError(f'У договорі "{order.td_agreement_id.name}" не вказана дата початку.')

        company = self.company_id
        company_partner = company.partner_id
        warehouse_manager_id = company.td_warehouse_manager_id
        medical_manager_id = company.td_medical_warehouse_manager_id
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
                'warehouse_manager': warehouse_manager_id.td_partner_short_name or warehouse_manager_id.name,
                'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.name,
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
            'act_date': self.td_custody_act_date.strftime('%d.%m.%Y'),
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

    def td_get_report_refund_data(self):
        """
        Preparation of data for the refund act report
        """
        self.ensure_one()
        company = self.company_id
        company_partner = company.partner_id
        partner = self.partner_id
        medical_manager_id = company.td_medical_warehouse_manager_id.work_contact_id
       
        data = {
            'vendor_name': partner.full_partner_name or partner.name,
            'vendor_address': partner.contact_address_complete,
            'vendor_physical_address': self.td_parent_partner_id.contact_address_complete,
            'vendor_phone': partner.phone or '',
            'recipient_name': company_partner.full_partner_name,
            'recipient_registry': company.company_registry,
            'recipient_phone': company_partner.phone or '',
            'recipient_address': company_partner.contact_address_complete,
            'recipient_bank_account': company_partner.bank_ids[0].acc_number,
            'recipient_bank_name': company_partner.bank_ids[0].bank_name,
            'recipient_bank_bic': company_partner.bank_ids[0].bank_bic,
            'recipient_vat': company.vat or '',
            'recipient_ref': company_partner.ref or '',
            'recipient_address': company_partner.contact_address_complete,
            'recipient_physical_address': company_partner.contact_address_complete,
            'document_number': self.name.split('/')[-1],
            'document_date': format_date(self.env, self.date_done, date_format='dd MMMM yyyy p.'),
            'tax_guide_name': self.sale_id.td_tax_guide_id.name,
            'lines': [],
            'amount_untaxed': self.td_total_without_tax,
            'amount_tax': self.td_total_tax,
            'amount_total': self.td_total_amount,
            'amount_in_words': self.get_amount_in_words(),
            'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.full_partner_name,
        }

        line_num = 0
        for move in self.move_ids_without_package:
            line_num += 1
            move_line_ids = move.mapped('move_line_ids')
            
            line_data = {
                'sequence': line_num,
                'product_serial_numbers': [
                    l.name for l in move_line_ids.mapped('lot_id')]
                    if move_line_ids else [],
                'expiration_dates': [
                    d.strftime('%d.%m.%Y') for d in move_line_ids.mapped('expiration_date')]
                    if move_line_ids else [],
                'storage_conditions': move.location_id.mapped('td_condition_ids.name'),
                'product_name': move.product_id.description_sale or move.product_id.name,
                'product_manufacturer': move.product_id.td_manufacturer_directory_res_id.name or '',
                'uom': move.product_uom.name,
                'quantity': move.product_uom_qty,
                'price_unit': move.td_price_unit,
                'price_taxes': move.td_taxes_price,
                'price_subtotal': move.td_price_total,
                'price_total': move.td_price_total,
            }
            data['lines'].append(line_data)

        return data
