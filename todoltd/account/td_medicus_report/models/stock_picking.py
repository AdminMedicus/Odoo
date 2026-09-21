# -*- coding: utf-8 -*-
from datetime import datetime

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
        string='TD Implementation Document',
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

    # ---------------------------------------------------------
    # TTH / TTN
    # ---------------------------------------------------------
    td_ttn_transport_type = fields.Selection(
        selection=[
            ('own', 'Own Vehicle'),
            ('hired', 'Third-Party Carrier'),
        ],
        string='Transportation Type',
        default='own',
        copy=False,
    )

    td_ttn_vehicle_id = fields.Many2one(
        comodel_name='fleet.vehicle',
        string='Vehicle',
        domain="[('td_transport_ownership', '=', 'own')]",
        copy=False,
    )

    td_ttn_hired_vehicle = fields.Char(
        string='Hired Vehicle',
        copy=False,
    )

    td_ttn_driver_employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Driver (Employee)',
        copy=False,
    )

    td_ttn_driver_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Driver (Contact)',
        copy=False,
    )

    td_ttn_hired_driver = fields.Char(
        string='Driver',
        copy=False,
    )

    td_ttn_carrier_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Road Carrier',
        copy=False,
    )

    td_ttn_hired_carrier = fields.Char(
        string='Hired Road Carrier',
        copy=False,
    )

    td_ttn_driver_license_number = fields.Char(
        string='Driver License Number',
        copy=False,
    )

    td_ttn_driver_forwarder = fields.Char(
        string='Driver-Forwarder',
        copy=False,
    )

    td_ttn_places_count = fields.Char(
        string='Number of Places',
        copy=False,
    )

    td_ttn_gross_weight = fields.Float(
        string='Gross Weight (tons)',
        # digits=(16, 3),
        copy=False,
    )

    td_ttn_vehicle_dimensions_manual = fields.Boolean(
        string='Vehicle dimensions entered manually',
        default=False,
        copy=False,
    )

    td_ttn_vehicle_length = fields.Float(
        string='Length, m',
        digits=(16, 3),
        compute='_compute_td_ttn_vehicle_dimensions',
        inverse='_inverse_td_ttn_vehicle_dimensions',
        store=True,
        readonly=False,
        copy=False,
    )

    td_ttn_vehicle_width = fields.Float(
        string='Width, m',
        digits=(16, 3),
        compute='_compute_td_ttn_vehicle_dimensions',
        inverse='_inverse_td_ttn_vehicle_dimensions',
        store=True,
        readonly=False,
        copy=False,
    )

    td_ttn_vehicle_height = fields.Float(
        string='Height, m',
        digits=(16, 3),
        compute='_compute_td_ttn_vehicle_dimensions',
        inverse='_inverse_td_ttn_vehicle_dimensions',
        store=True,
        readonly=False,
        copy=False,
    )

    td_ttn_license_number = fields.Char(
        string='License Plate',
        copy=False,
        related='td_ttn_vehicle_id.license_plate',
        readonly=False
    )

    td_ttn_license_number_other = fields.Char(
        string='License Plate Other',
        copy=False,
    )

    @api.depends(
        'td_ttn_vehicle_id',
        'td_ttn_vehicle_id.td_body_length',
        'td_ttn_vehicle_id.td_body_width',
        'td_ttn_vehicle_id.td_body_height',
        'td_ttn_vehicle_dimensions_manual',
    )
    def _compute_td_ttn_vehicle_dimensions(self):
        for rec in self:
            if rec.td_ttn_vehicle_id and not rec.td_ttn_vehicle_dimensions_manual:
                rec.td_ttn_vehicle_length = rec.td_ttn_vehicle_id.td_body_length
                rec.td_ttn_vehicle_width = rec.td_ttn_vehicle_id.td_body_width
                rec.td_ttn_vehicle_height = rec.td_ttn_vehicle_id.td_body_height

    @api.onchange('td_ttn_vehicle_id')
    def _onchange_td_ttn_vehicle_id(self):
        for rec in self:
            if rec.td_ttn_vehicle_id:
                rec.td_ttn_vehicle_dimensions_manual = False
                rec.td_ttn_vehicle_length = rec.td_ttn_vehicle_id.td_body_length
                rec.td_ttn_vehicle_width = rec.td_ttn_vehicle_id.td_body_width
                rec.td_ttn_vehicle_height = rec.td_ttn_vehicle_id.td_body_height

    def _inverse_td_ttn_vehicle_dimensions(self):
        for rec in self:
            rec.td_ttn_vehicle_dimensions_manual = True

    @api.onchange('td_ttn_transport_type')
    def _onchange_td_ttn_transport_type(self):
        for rec in self:
            rec.td_ttn_driver_license_number = False
            rec.td_ttn_driver_forwarder = False

            if rec.td_ttn_transport_type == 'own':
                rec.td_ttn_driver_partner_id = False
                rec.td_ttn_carrier_partner_id = rec.company_id.partner_id if rec.company_id.partner_id else False
            else:
                rec.td_ttn_driver_employee_id = False
                rec.td_ttn_vehicle_id = False
                rec.td_ttn_vehicle_length = 0.0
                rec.td_ttn_vehicle_width = 0.0
                rec.td_ttn_vehicle_height = 0.0

    @api.onchange('td_ttn_driver_employee_id')
    def _onchange_td_ttn_driver_employee_id(self):
        for rec in self:
            if rec.td_ttn_transport_type != 'own':
                continue

            user = rec.td_ttn_driver_employee_id
            if not user:
                rec.td_ttn_driver_license_number = False
                rec.td_ttn_driver_forwarder = False
                return

            partner = user.work_contact_id or user.user_id.partner_id
            rec.td_ttn_carrier_partner_id = rec.company_id.partner_id if rec.company_id.partner_id else False
            rec.td_ttn_driver_license_number = user.td_driver_license_number if user else False
            rec.td_ttn_driver_forwarder = (
                partner.full_partner_name if partner and partner.full_partner_name else user.name
            )

    @api.onchange('td_ttn_driver_partner_id')
    def _onchange_td_ttn_driver_partner_id(self):
        for rec in self:
            if rec.td_ttn_transport_type != 'hired':
                continue

            partner = rec.td_ttn_driver_partner_id
            if not partner:
                rec.td_ttn_carrier_partner_id = False
                rec.td_ttn_driver_license_number = False
                rec.td_ttn_driver_forwarder = False
                return

            rec.td_ttn_carrier_partner_id = partner.commercial_partner_id
            # rec.td_ttn_driver_license_number = partner.td_driver_license_number or False
            rec.td_ttn_driver_forwarder = partner.full_partner_name or partner.name or False

    def _compute_td_show_create_invoice_button(self):
        for picking in self:
            if picking.td_order_implementation_document == 'exp_inv':
                pickings = picking.sale_id.picking_ids.filtered(
                    lambda p: p.picking_type_code in ['internal', 'outgoing']
                )
                all_pickings_done = all(p.state == 'done' for p in pickings)
                picking.td_show_create_invoice_button = (
                    picking.picking_type_code in ['internal', 'outgoing']
                    and all_pickings_done
                    and not picking.sale_id.td_invoice_from_delivery
                )
            elif picking.td_order_implementation_document == 'act_res_st':
                picking.td_show_create_invoice_button = (
                    picking.picking_type_code == 'incoming'
                    and picking.state == 'done'
                    and bool(picking.return_id)
                    and not picking.sale_id.td_invoice_from_delivery
                )
            else:
                picking.td_show_create_invoice_button = False

    def _compute_td_show_create_custody_act_button(self):
        for picking in self:
            picking.td_show_create_custody_act_button = (
                picking.state == 'done'
                and picking.picking_type_code in ['outgoing', 'incoming']
                and (
                    picking.td_order_implementation_document == 'act_res_st'
                    or picking.implementation_document == 'act_res_st'
                )
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
        invoice = self.env['account.move'].browse(invoice_action['res_id'])

        if invoice:
            invoice.invoice_date = self.td_invoice_date or datetime.now().date()
            invoice.action_post()
            sale_order.td_invoice_from_delivery = True
            sale_order.picking_ids.write({
                'td_invoice_for_pick_id': invoice.id,
            })

            return self.env.ref('td_medicus_report.action_report_wholesale_invoice_invoice').report_action(invoice)

    def td_create_custody_act(self):
        """
        Create custody act from delivery order and print it
        """
        self.ensure_one()
        if not self.td_custody_act_date:
            self.td_custody_act_date = datetime.now().date()

        if self.picking_type_code == 'outgoing' and self.implementation_document == 'act_res_st':
            return self.env.ref('td_medicus_report.action_report_custody_transfer_act').report_action(self)
        elif self.picking_type_code == 'incoming' and self.implementation_document == 'act_res_st':
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
            amount = sum(
                move.td_price_subtotal
                for move in self.move_ids_without_package
                if hasattr(move, 'td_price_subtotal')
            )

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
        delivery_datetime_utc = self.date_deadline or self.date_done
        user_tz = self.env.user.tz or 'UTC'
        delivery_datetime = fields.Datetime.context_timestamp(self.with_context(tz=user_tz), delivery_datetime_utc)

        partner = self.partner_id
        current_user = self.env.user.partner_id

        shipping_contacts = order.partner_shipping_id.child_ids.filtered(
            lambda p: p.type == 'contact' and p.td_is_counterparty_physical_person
        )

        shipping_partner = shipping_contacts[0] if shipping_contacts else order.partner_shipping_id

        data = {
            'name': self.name.split('/')[-1] if self.name else '',
            'date': self.date_done.strftime('%d.%m.%Y') if self.date_done else '',
            'company_logo': self.company_id.logo,
            'warehouse_name': self.location_id.warehouse_id.name,
            'location_barcode': self.location_id.barcode,
            'partner_name': partner.full_partner_name or partner.name,
            'employee_name': current_user.full_partner_name or current_user.name,
            'employee_short_name': current_user.td_partner_short_name or current_user.name,
            'document': dict(self._fields['implementation_document']._description_selection(self.env)).get(self.implementation_document, ''),
            'delivery_address': self.warehouse_address_id.contact_address_complete or self.warehouse_address_id.name,
            # 'delivery_address': order.partner_shipping_id.contact_address_complete,
            'delivery_method': partner.property_delivery_carrier_id.name,
            'recipient_name': shipping_partner.full_partner_name or shipping_partner.name,
            'return_recipient_name': self.location_dest_id.warehouse_id.name,
            'return_manager': self.env.user.full_partner_name or self.env.user.name or '',
            'recipient_phone': shipping_partner.phone,
            'delivery_time': delivery_datetime.strftime('%H:%M'),
            'delivery_date': delivery_datetime.strftime('%d.%m.%Y'),
            'lines': [],
            'amount_account_untaxed': 0,
            'amount_untaxed': self.td_total_without_tax,
            'amount_account_tax': 0,
            'amount_tax': self.td_total_tax,
            'amount_account_total': 0,
            'amount_total': self.td_total_amount,
            'amount_account_in_words': '',
            'amount_in_words': self.get_amount_in_words(),
            'amount_tax_in_words': self._amount_to_words_ua(self.td_total_tax),
            'tax_guide_name': order.td_tax_guide_id.name if order and order.td_tax_guide_id else '',
        }

        line_num = 0
        for move in self.move_ids_without_package:
            product = move.product_id
            base_product_name = product.description_sale or product.name
            manufacturer = product.td_manufacturer_directory_res_id.name if product.td_manufacturer_directory_res_id else ''
            default_code = product.default_code or ''
            move_line_ids = move.move_line_ids

            # Group move lines by lot for batch quantity transparency
            lots = {}
            for ml in move_line_ids:
                lot_key = ml.lot_id.id or 0
                if lot_key in lots:
                    lots[lot_key]['quantity'] += ml.quantity
                else:
                    lots[lot_key] = {
                        'lot_id': ml.lot_id,
                        'quantity': ml.quantity,
                        'expiration_date': ml.expiration_date,
                        'location_id': ml.location_id,
                    }

            for lot_info in lots.values():
                line_num += 1
                lot = lot_info['lot_id']
                serial_name = lot.name if lot else ''
                product_name = base_product_name
                if serial_name:
                    product_name = '%s (%s)' % (base_product_name, serial_name)

                exp_date = (
                    lot_info['expiration_date'].strftime('%d.%m.%Y')
                    if lot_info['expiration_date'] else None
                )
                qty = lot_info['quantity']

                line_data = {
                    'sequence': line_num,
                    'product_name': product_name,
                    'product_manufacturer': manufacturer,
                    'quantity': qty,
                    'customs_value': 0,
                    'price_untaxed': move.td_untaxed_price_unit,
                    'price_unit': move.td_price_unit,
                    'account_price': 0,
                    'price_subtotal': move.td_untaxed_price_unit * qty,
                    'price_total': move.td_price_unit * qty,
                    'account_total': 0,
                    'markup_coefficient': 0,
                    'default_code': default_code,
                    'product_serial_numbers': [serial_name] if serial_name else [],
                    'registration_certificate': '',
                    'quality_certificate': '',
                    'expiration_dates': [exp_date] if exp_date else [],
                    'stock_inventory': lot_info['location_id'].complete_name if lot_info['location_id'] else '',
                }
                data['lines'].append(line_data)

        return data

    def _get_waybill_transport_info(self, transport_type):
        """Return waybill_info dict depending on transport ownership type."""
        self.ensure_one()
        common = {
            'transport_type': transport_type,
            'places_count': self._amount_to_words_ua(float(self.td_ttn_places_count), count=True) if self.td_ttn_places_count else '',
            'gross_weight': self._amount_to_words_ua(float(self.td_ttn_gross_weight), weight=True) if self.td_ttn_gross_weight else '',
            'driver_forwarder': self.td_ttn_driver_forwarder or '',
            'vehicle_length': self.td_ttn_vehicle_length or '',
            'vehicle_width': self.td_ttn_vehicle_width or '',
            'vehicle_height': self.td_ttn_vehicle_height or '',
        }
        if self.td_ttn_transport_type == 'own':
            common.update({
                'vehicle': self.td_ttn_vehicle_id.name.replace('/', ' ') if self.td_ttn_vehicle_id else '',
                'driver': self.td_ttn_driver_employee_id.name if self.td_ttn_driver_employee_id else '',
                'driver_license': self.td_ttn_driver_license_number or '',
                'carrier_partner': self.td_ttn_carrier_partner_id.full_partner_name if self.td_ttn_carrier_partner_id else '',
            })
        else:
            common.update({
                'vehicle': self.td_ttn_hired_vehicle or '',
                'driver': self.td_ttn_hired_driver or '',
                'driver_license': self.td_ttn_driver_license_number or '',
                'carrier_partner': self.td_ttn_hired_carrier or '',
            })
        return common

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
        transport_type = dict(self._fields['td_ttn_transport_type']._description_selection(self.env)).get(self.td_ttn_transport_type, '')

        document = self.td_invoice_for_pick_id
        if not document:
            posted_invoices = order.invoice_ids.filtered(lambda i: i.state == 'posted')
            document = posted_invoices[-1] if posted_invoices else None

        if self.implementation_document != 'exp_inv':
            document = self

        document_name = document.name if document else ''
        document_date = document.invoice_date if document and self.implementation_document == 'exp_inv' else document.date_done

        data = {
            'waybill_number': self.name.split('/')[-1],
            'waybill_date': format_date(self.env, self.date_done, date_format='dd MMMM yyyy p.'),
            'buyer': order.partner_invoice_id.full_partner_name or order.partner_invoice_id.name,
            'shipper': company.partner_id.full_partner_name,
            'shipper_code': company.partner_id.company_registry or '',
            'consignee': partner.full_partner_name or partner.name,
            'consignee_code': partner.company_registry or '',
            'delivery_address': partner.contact_address_complete,
            'loading_point': self.warehouse_address_id.contact_address_complete,
            'place_of_issue': self.warehouse_address_id.state_id.name,
            'warehouse_manager': warehouse_manager_id.td_partner_short_name or warehouse_manager_id.name,
            'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.name,
            'accompanying_document': document_name.split('/')[-1] if document_name else '',
            'accompanying_document_date': document_date.strftime('%d.%m.%Y') if document_date else '',
            'accompanying_document_full_date': format_date(
                self.env,
                document_date,
                date_format='dd MMMM yyyy p.'
            ) if document_date else '',
            'total_amount': self._amount_to_words_ua(self.td_total_amount),
            'tax_amount': self._amount_to_words_ua(self.td_total_tax),
            'total': self.td_total_amount,
            'full_description': """
            (повне найменування (прізвище (за наявності), власне ім'ята по-батькові (за наявності), унікальний номер запису в Єдиному державному демографічному реєстрі (за наявності), код платника податків згідно з Єдиним державним реєстром підприємств та організацій України або податковий номер (реєстраційний номер обліковойї картки платника податків або серія (за наявності) та номер паспорта громадянина України (для фізичних осіб, які через свої релігійні переконання відмовляються від прийняття реєстраційного номера облікової картки платника податків та повідомили про це відповідний контролюючий орган і мають відмітку в паспорті))))
            """,
            'lines': [],
            'waybill_info': self._get_waybill_transport_info(transport_type),
        }

        line_num = 0
        for move in self.move_ids_without_package:
            line_num += 1

            line_data = {
                'sequence': line_num,
                'product_name': move.product_id.description_sale or move.product_id.name,
                'uom': move.product_uom.name,
                'quantity': move.product_uom_qty,
                'price_unit': move.td_untaxed_price_unit,
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
        company = self.company_id
        company_partner = company.partner_id
        warehouse_manager_id = company.td_warehouse_manager_id
        medical_manager_id = company.td_medical_warehouse_manager_id
        client_partner = self.td_parent_partner_id
        shipper_partner = self.partner_id
        partner_name = (
            client_partner.parent_id.full_partner_name or
            client_partner.parent_id.name or
            client_partner.full_partner_name or
            client_partner.name
        )

        data = {
            'company': {
                'name': company_partner.full_partner_name or company_partner.name,
                'registry': company.company_registry,
                'vat': company.vat,
                'street': company_partner.contact_address_complete,
                'logo': company.logo,
                'ref': company_partner.ref or '',
                'bank_account': company_partner.bank_ids[0].acc_number,
                'bank_name': company_partner.bank_ids[0].bank_name,
                'bank_bic': company_partner.bank_ids[0].bank_bic,
                'tax_position': company_partner.property_account_position_id.name,
                'warehouse_manager': warehouse_manager_id.td_partner_short_name or warehouse_manager_id.name,
                'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.name,
                'warehouse_address': self.warehouse_address_id.contact_address_complete or self.warehouse_address_id.name
            },
            'partner': {
                'name': partner_name,
                'registry': client_partner.company_registry,
                'street': client_partner.parent_id.contact_address_complete,
                'fisical_address': shipper_partner.contact_address_complete,
                'executant_name': shipper_partner.full_partner_name or shipper_partner.display_name,
            },
            'lines': [],
            'act_number': self.name.split('/')[-1],
            'act_date': self.td_custody_act_date.strftime('%d.%m.%Y') if self.td_custody_act_date else self.date_done.strftime('%d.%m.%Y'),
            'agreement_number': '',
            'agreement_date': '',
            'transfer_title': 'Акт передачі майна на відповідальне зберігання № ',
            'return_title': 'Акт повернення майна з відповідального зберігання № ',
            'transfer_subtitle': 'Депонент передав, а виконавець прийняв на відповідальне зберігання наступне майно:',
            'return_subtitle': 'Депонент прийняв, а виконавець повернув з відповідального зберігання наступне майно:',
            'amount_total': self.td_amount_origin_currency,
            'amount_in_words': self.get_amount_in_words(),
        }

        if order.td_agreement_id:
            agreement_date = order.td_agreement_id.start_date
            data['agreement_number'] = order.td_agreement_id.agreement_number or ''
            data['agreement_date'] = agreement_date.strftime('%d.%m.%Y') if agreement_date else ''

        line_num = 0
        for line in self.move_ids_without_package:
            if not line.product_id:
                continue
            location = line.location_id
            location_dest = line.location_dest_id
            move_line_ids = line.mapped('move_line_ids')

            if move_line_ids:
                for ml in move_line_ids:
                    line_num += 1
                    qty = ml.quantity
                    serial_name = ml.lot_id.name if ml.lot_id else ''
                    exp_date = (
                        ml.expiration_date.strftime('%d.%m.%Y')
                        if ml.expiration_date else None
                    )

                    line_data = {
                        'sequence': line_num,
                        'product_name': line.product_id.description_sale,
                        'product_code': line.product_id.default_code or '',
                        'product_serial_numbers': [serial_name] if serial_name else [],
                        'product_catalog_number': line.product_id.default_code or '',
                        'product_manufacturer': line.product_id.td_manufacturer_directory_res_id.name or '',
                        'storage_conditions': location.mapped('td_condition_ids.name'),
                        'storage_conditions_dest': location_dest.mapped('td_condition_ids.name'),
                        'quantity': qty,
                        'uom': line.product_uom.name,
                        'expiration_dates': [exp_date] if exp_date else [],
                        'price_unit': line.td_untaxed_price_unit,
                        'price_subtotal': line.td_untaxed_price_unit * qty,
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
                    'uom': line.product_uom.name,
                    'expiration_dates': [],
                    'price_unit': line.td_untaxed_price_unit,
                    'price_subtotal': line.td_price_subtotal,
                }
                data['lines'].append(line_data)

        return data

    def td_get_custody_balance_data(self):
        """
        Preparation of data for the custody balance report.
        Shows what's still in custody storage by partner.
        Finds all custody transfers (outgoing) and calculates remaining balance
        after subtracting returns (incoming).
        """
        self.ensure_one()

        company = self.company_id
        company_partner = company.partner_id
        client_partner = self.td_parent_partner_id
        shipper_partner = self.partner_id
        warehouse_manager_id = company.td_warehouse_manager_id
        partner_name = (
            client_partner.parent_id.full_partner_name or
            client_partner.parent_id.name or
            client_partner.full_partner_name or
            client_partner.name
        )

        data = {
            'company': {
                'name': company_partner.full_partner_name or company_partner.name,
                'registry': company_partner.company_registry,
                'vat': company_partner.vat,
                'street': company_partner.contact_address_complete,
                'ref': company_partner.ref or '',
                'bank_account': company_partner.bank_ids[0].acc_number if company_partner.bank_ids else '',
                'bank_name': company_partner.bank_ids[0].bank_name if company_partner.bank_ids else '',
                'bank_bic': company_partner.bank_ids[0].bank_bic if company_partner.bank_ids else '',
                'warehouse_manager': warehouse_manager_id.td_partner_short_name or warehouse_manager_id.name if warehouse_manager_id else '',
            },
            'partner': {
                'name': partner_name,
                'street': client_partner.parent_id.contact_address_complete or client_partner.contact_address_complete,
                'registry': client_partner.company_registry,
                'fisical_address': self.warehouse_address_id.contact_address_complete,
                'executant_name': shipper_partner.full_partner_name or shipper_partner.display_name,
            },
            'lines': [],
            'documents': [],
            'act_date': fields.Date.today().strftime('%d.%m.%y'),
            'agreement_number': '',
            'agreement_date': '',
            'amount_total': 0.0,
            'amount_in_words': '',
        }

        outgoing_pickings = self.env['stock.picking'].search([
            ('picking_type_code', '=', 'outgoing'),
            ('td_order_implementation_document', '=', 'act_res_st'),
            ('state', '=', 'done'),
            ('td_parent_partner_id', '=', client_partner.id),
        ])

        product_balances = {}

        for picking in outgoing_pickings:
            sale_order = picking.sale_id
            if not sale_order:
                continue

            for move in picking.move_ids_without_package:
                if not move.product_id:
                    continue

                move_line_ids = move.mapped('move_line_ids')

                for move_line in move_line_ids:
                    lot_id = move_line.lot_id
                    key = (sale_order.id, move.product_id.id, lot_id.id if lot_id else 0)

                    if key not in product_balances:
                        product_balances[key] = {
                            'sale_order': sale_order,
                            'product': move.product_id,
                            'lot': lot_id,
                            'transferred': 0.0,
                            'returned': 0.0,
                            'price_unit': move.td_untaxed_price_unit if hasattr(move, 'td_untaxed_price_unit') else 0,
                            'expiration_date': move_line.expiration_date,
                        }

                    product_balances[key]['transferred'] += move_line.quantity

        incoming_pickings = self.env['stock.picking'].search([
            ('picking_type_code', '=', 'incoming'),
            ('implementation_document', '=', 'act_res_st'),
            ('state', '=', 'done'),
            ('td_parent_partner_id', '=', client_partner.id),
        ])

        for picking in incoming_pickings:
            for move in picking.move_ids_without_package:
                if not move.product_id:
                    continue

                sale_order = picking.sale_id
                if not sale_order:
                    continue

                move_line_ids = move.mapped('move_line_ids')

                for move_line in move_line_ids:
                    lot_id = move_line.lot_id
                    key = (sale_order.id, move.product_id.id, lot_id.id if lot_id else 0)

                    if key in product_balances:
                        product_balances[key]['returned'] += move_line.quantity

        line_num = 0
        amount_total = 0.0
        documents_dict = {}

        for key, balance_data in product_balances.items():
            remaining_qty = balance_data['transferred'] - balance_data['returned']

            if remaining_qty > 0:
                line_num += 1

                sale_order = balance_data['sale_order']
                product = balance_data['product']
                lot = balance_data['lot']

                line_amount = remaining_qty * balance_data['price_unit']
                amount_total += line_amount

                serial_display = lot.name if lot else ''
                expiry_display = balance_data['expiration_date'].strftime('%d.%m.%Y') if balance_data['expiration_date'] else ''

                line_data = {
                    'sequence': line_num,
                    'document': sale_order.name,
                    'product_name': product.description_sale or product.name,
                    'product_manufacturer': product.td_manufacturer_directory_res_id.name or '',
                    'serial': serial_display,
                    'expiry_date': expiry_display,
                    'quantity': remaining_qty,
                    'price_unit': balance_data['price_unit'],
                    'amount': line_amount,
                }

                doc_name = sale_order.name
                if doc_name not in documents_dict:
                    documents_dict[doc_name] = {
                        'document_name': doc_name,
                        'document_date': sale_order.date_order.strftime('%d.%m.%Y'),
                        'agreement_number': sale_order.td_agreement_id.agreement_number if sale_order.td_agreement_id else '',
                        'agreement_date': sale_order.td_agreement_id.start_date.strftime('%d.%m.%Y') if sale_order.td_agreement_id and sale_order.td_agreement_id.start_date else '',
                        'lines': [],
                        'subtotal': 0.0,
                    }

                documents_dict[doc_name]['lines'].append(line_data)
                documents_dict[doc_name]['subtotal'] += line_amount

        data['documents'] = list(documents_dict.values())
        data['amount_total'] = amount_total

        if documents_dict:
            agreements = set()
            for doc_data in documents_dict.values():
                agreement_key = (doc_data.get('agreement_number', ''), doc_data.get('agreement_date', ''))
                agreements.add(agreement_key)

            if len(agreements) == 1:
                agreement_number, agreement_date = agreements.pop()
                if agreement_number or agreement_date:
                    data['agreement_number'] = agreement_number
                    data['agreement_date'] = agreement_date

        if amount_total:
            data['amount_in_words'] = self._amount_to_words_ua(amount_total)
        else:
            data['amount_in_words'] = ''

        return data

    def td_get_report_refund_data(self):
        """
        Preparation of data for the refund act report
        """
        self.ensure_one()
        company = self.company_id
        company_partner = company.partner_id
        partner = self.partner_id
        manager_id = company.td_warehouse_manager_id
        medical_manager_id = company.td_medical_warehouse_manager_id

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
            'recipient_physical_address': self.location_dest_id.warehouse_id.partner_id.contact_address_complete,
            'document_number': self.name.split('/')[-1],
            'document_date': format_date(self.env, self.date_done, date_format='dd MMMM yyyy p.'),
            'tax_guide_name': self.sale_id.td_tax_guide_id.name,
            'lines': [],
            'amount_untaxed': self.td_total_without_tax,
            'amount_tax': self.td_total_tax,
            'amount_total': self.td_total_amount,
            'amount_in_words': self.get_amount_in_words(),
            'warehouse_manager': manager_id.td_partner_short_name or manager_id.name,
            'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.name,
        }

        line_num = 0
        for move in self.move_ids_without_package:
            line_num += 1
            move_line_ids = move.mapped('move_line_ids')
            location = move.move_orig_ids.mapped('location_id') or move.location_id

            line_data = {
                'sequence': line_num,
                'product_serial_numbers': [l.name for l in move_line_ids.mapped('lot_id')] if move_line_ids else [],
                'expiration_dates': [
                    d.strftime('%d.%m.%Y') if d else ''
                    for d in move_line_ids.mapped('expiration_date')
                ] if move_line_ids else [],
                'storage_conditions': location.mapped('td_condition_ids.name'),
                'product_name': move.product_id.description_sale or move.product_id.name,
                'product_manufacturer': move.product_id.td_manufacturer_directory_res_id.name or '',
                'uom': move.product_uom.name,
                'quantity': move.product_uom_qty,
                'price_unit': move.td_price_unit,
                'untaxed_price_unit': move.td_untaxed_price_unit,
                'price_taxes': move.td_taxes_price,
                'price_subtotal': move.td_price_subtotal,
                'price_total': move.td_price_total,
            }
            data['lines'].append(line_data)

        return data

    def td_get_vendor_refund_act_data(self):
        """
        Preparation of data for the vendor refund act report
        """
        self.ensure_one()

        company = self.company_id
        company_partner = company.partner_id
        vendor_partner = self.partner_id
        sale_order = self.sale_id

        invoice_partner = sale_order.partner_invoice_id if sale_order and sale_order.partner_invoice_id else vendor_partner
        shipping_partner = sale_order.partner_shipping_id if sale_order and sale_order.partner_shipping_id else vendor_partner
        vendor_recipient = vendor_partner.child_ids.filtered(lambda p: p.type == 'contact' and p.use_in_vendor_refund_report)
        vendor_recipient_name = vendor_recipient[0].full_partner_name or vendor_recipient[0].name if vendor_recipient else ''
        
        payment_partner = None
        if sale_order and sale_order.partner_invoice_id and sale_order.partner_invoice_id != vendor_partner:
            agreement = sale_order.td_agreement_id
            payment_partner = {
                'name': sale_order.partner_invoice_id.full_partner_name or sale_order.partner_invoice_id.name,
                'street': sale_order.partner_invoice_id.contact_address_complete or '',
                'agreement': agreement.name if agreement else '',
                'agreement_date': format_date(self.env, agreement.start_date, date_format='dd.MM.yyyy') if agreement and agreement.start_date else '',
                'payment_term': sale_order.payment_term_id.name if sale_order.payment_term_id else '',
            }

        manager_id = company.td_warehouse_manager_id
        medical_manager_id = company.td_medical_warehouse_manager_id
        warehouse_address = self.location_dest_id.warehouse_id.partner_id.contact_address_complete if self.location_dest_id.warehouse_id else ''

        company_bank = company_partner.bank_ids[0] if company_partner.bank_ids else None
        recipient_bank = invoice_partner.bank_ids[0] if invoice_partner.bank_ids else None

        company_tax_position = ''
        if company_partner.property_account_position_id:
            company_tax_position = company_partner.property_account_position_id.name

        data = {
            'vendor_name': company_partner.full_partner_name or company_partner.name,
            'vendor_registry': company.company_registry or '',
            'vendor_vat': company.vat or '',
            'vendor_address': company_partner.contact_address_complete or '',
            'vendor_physical_address': self.location_dest_id.warehouse_id.partner_id.contact_address_complete if self.location_dest_id.warehouse_id else company_partner.contact_address_complete or '',
            'vendor_phone': company_partner.phone or '',
            'vendor_bank_account': company_bank.acc_number if company_bank else '',
            'vendor_bank_name': company_bank.bank_id.name if company_bank and company_bank.bank_id else '',
            'vendor_bank_bic': company_bank.bank_bic if company_bank else '',
            'vendor_ref': company_partner.ref or '',
            'vendor_tax_position': company_tax_position,
            'vendor_recipient': vendor_recipient_name,

            'recipient_name': invoice_partner.full_partner_name or invoice_partner.name,
            'recipient_registry': invoice_partner.company_registry or company.company_registry or '',
            'recipient_phone': invoice_partner.phone or '',
            'recipient_bank_account': recipient_bank.acc_number if recipient_bank else '',
            'recipient_bank_name': recipient_bank.bank_id.name if recipient_bank and recipient_bank.bank_id else '',
            'recipient_bank_bic': recipient_bank.bank_bic if recipient_bank else '',
            'recipient_vat': invoice_partner.vat or company.vat or '',
            'recipient_ref': invoice_partner.ref or '',
            'recipient_address': invoice_partner.street or invoice_partner.contact_address_complete or '',
            'recipient_physical_address': shipping_partner.contact_address_complete or '',

            'payment_partner': payment_partner,

            'document_number': self.name.split('/')[-1] if '/' in self.name else self.name,
            'document_date': format_date(self.env, self.date_done, date_format='dd.MM.yyyy') if self.date_done else '',

            'tax_guide_name': sale_order.td_tax_guide_id.name if sale_order and sale_order.td_tax_guide_id else 'ПДВ',

            'amount_in_words': self.get_amount_in_words(),
            'amount_untaxed': self.td_total_without_tax or 0.0,
            'amount_tax': self.td_total_tax or 0.0,
            'amount_total': self.td_total_amount or 0.0,

            'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.name if medical_manager_id else '',
            'warehouse_manager': manager_id.td_partner_short_name or manager_id.name if manager_id else '',
            'warehouse_address': warehouse_address,

            'company': {
                'medical_warehouse_manager': medical_manager_id.td_partner_short_name or medical_manager_id.name if medical_manager_id else '',
                'warehouse_manager': manager_id.td_partner_short_name or manager_id.name if manager_id else '',
                'warehouse_address': warehouse_address,
            },

            'lines': [],
        }

        line_num = 0
        for move in self.move_ids_without_package:
            move_line_ids = move.mapped('move_line_ids')
            location = move.location_id
            storage_conditions = location.mapped('td_condition_ids.name')
            supplier_doc_number = self.td_supplier_document or ''
            supplier_doc_date = self.td_date_supplier_document.strftime('%d.%m.%Y') if self.td_date_supplier_document else ''
            price_untaxed = move.td_untaxed_price_unit if hasattr(move, 'td_untaxed_price_unit') else 0.0

            # Group move lines by lot
            lots = {}
            for ml in move_line_ids:
                lot_key = ml.lot_id.id or 0
                if lot_key in lots:
                    lots[lot_key]['quantity'] += ml.quantity
                else:
                    lots[lot_key] = {
                        'lot_id': ml.lot_id,
                        'quantity': ml.quantity,
                        'expiration_date': (
                            ml.lot_id.expiration_date
                            if ml.lot_id and ml.lot_id.expiration_date
                            else ml.expiration_date
                        ),
                    }

            if not lots:
                lots[0] = {
                    'lot_id': False,
                    'quantity': move.product_uom_qty,
                    'expiration_date': False,
                }

            for lot_info in lots.values():
                line_num += 1
                lot = lot_info['lot_id']
                qty = lot_info['quantity']
                serial_name = lot.name if lot else ''
                exp_date = (
                    lot_info['expiration_date'].strftime('%d.%m.%Y')
                    if lot_info['expiration_date'] else ''
                )

                line_data = {
                    'sequence': line_num,
                    'product_name': move.product_id.description_sale or move.product_id.name,
                    'product_manufacturer': move.product_id.td_manufacturer_directory_res_id.name or '',
                    'product_serial_numbers': [serial_name] if serial_name else [],
                    'expiration_dates': [exp_date] if exp_date else [],
                    'storage_conditions': storage_conditions,
                    'supplier_document_number': supplier_doc_number,
                    'supplier_document_date': supplier_doc_date,
                    'quantity': qty,
                    'uom': move.product_uom.name,
                    'contract_price': getattr(move, 'td_contract_price', 0.0),
                    'customs_value': getattr(move, 'td_customs_value_good', 0.0),
                    'supplier_markup': getattr(move, 'td_supplier_markup', 0.0),
                    'price_untaxed': price_untaxed,
                    'price_subtotal': price_untaxed * qty,
                }
                data['lines'].append(line_data)

        return data

