# -*- coding: utf-8 -*-
from odoo import models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def td_get_completion_act_data(self):
        """
        Preparation of data for the completion act report
        """
        self.ensure_one()

        company = self.company_id or self.env.company
        sale_order = self.td_sale_order_id
        partner = sale_order.partner_id if sale_order else self.env['res.partner']

        agreement = sale_order.td_agreement_id if sale_order else None
        agreement_name = agreement.name if agreement else ''
        agreement_number = agreement.agreement_number if agreement else ''
        agreement_date = agreement.start_date.strftime('%d.%m.%Y') if agreement and agreement.start_date else ''

        document_date = self.td_order_date.strftime('%d.%m.%Y') if self.td_order_date else ''
        doc_num = str(self.td_order_number) if self.td_order_number else ''
        document_number = doc_num.lstrip('0') or '0'

        commission_date = self.td_order_date.strftime('%d.%m.%Y') if self.td_order_date else '01.01.25'
        commission_number = str(self.td_order_number) if self.td_order_number else '02'

        company_ceo_name = (
            company.td_vice_president_id.td_partner_short_name or company.td_vice_president_id.name
        ) if company.td_vice_president_id else ''

        head_employee = self.td_head_commission or getattr(company, 'td_head_medical_equipment_sales_id', None)
        commission_head = head_employee.td_partner_short_name if head_employee else ''
        commission_head_job_title = head_employee.job_title if head_employee else ''

        if self.td_commission_members:
            commission_members = [
                {
                    'job_title': m.job_title or '',
                    'name': m.td_partner_short_name or m.name or '',
                }
                for m in self.td_commission_members
            ]
        else:
            commission_members = []
            for emp_field in ('td_warehouse_manager_id', 'td_medical_equipment_engineer_id'):
                emp = getattr(company, emp_field, None)
                if emp:
                    commission_members.append({
                        'job_title': emp.job_title or '',
                        'name': emp.td_partner_short_name or emp.name or '',
                    })

        wm = getattr(company, 'td_warehouse_manager_id', None)
        commission_medical_manager = wm.td_partner_short_name if wm else ''
        me = getattr(company, 'td_medical_equipment_engineer_id', None)
        commission_medical_engineer = me.td_partner_short_name if me else ''
        pm = getattr(company, 'td_medical_warehouse_manager_id', None)
        commission_pharmacy_manager = pm.td_partner_short_name if pm else ''

        data = {
            'company_name': company.partner_id.full_partner_name or company.name,
            'company_registry': company.company_registry or '',
            'company_ceo_name': company_ceo_name,
            'partner_name': (partner.full_partner_name or partner.name) if partner else '',
            'agreement_name': agreement_name,
            'agreement_number': agreement_number,
            'agreement_date': agreement_date,
            'document_number': document_number,
            'document_date': document_date,
            'corresponding_account': '28.1',
            'commission_date': commission_date,
            'commission_number': commission_number,
            'commission_head': commission_head,
            'commission_head_job_title': commission_head_job_title,
            'commission_members': commission_members,
            'commission_medical_manager': commission_medical_manager,
            'commission_pharmacy_manager': commission_pharmacy_manager,
            'commission_medical_engineer': commission_medical_engineer,
            'products': [],
            'documents': [],
        }

        if not sale_order:
            return data

        # Build lot map from done pickings of the sale order
        move_lots_by_product = {}
        for picking in sale_order.picking_ids.filtered(lambda p: p.state == 'done'):
            for move in picking.move_ids_without_package:
                lot_ids = getattr(move, 'td_lot_ids', None)
                lot_names = ', '.join(lot_ids.mapped('name')) if lot_ids else ''
                if move.product_id.id not in move_lots_by_product:
                    move_lots_by_product[move.product_id.id] = lot_names

        product_sequence = 0
        for order_line in sale_order.order_line:
            product = order_line.product_id
            product_sequence += 1

            product_price_unit = getattr(order_line, 'td_untaxed_price_unit', None) or order_line.price_unit or 0.0
            product_quantity = order_line.product_uom_qty
            product_price_subtotal = product_price_unit * product_quantity

            product_tax_rate = 0.0
            if product.taxes_id:
                product_tax_rate = product.taxes_id[0].amount

            product_uktzed = ''
            if hasattr(product, 'td_uktzed_code_id') and product.td_uktzed_code_id:
                product_uktzed = product.td_uktzed_code_id.code or product.td_uktzed_code_id.name or ''

            # Use self if it matches the product, otherwise search for the relevant BOM
            if (self.product_id == product or
                    (not self.product_id and self.product_tmpl_id == product.product_tmpl_id)):
                bom = self
            else:
                bom = self.env['mrp.bom'].search([
                    '|',
                    ('product_id', '=', product.id),
                    '&',
                    ('product_id', '=', False),
                    ('product_tmpl_id', '=', product.product_tmpl_id.id)
                ], limit=1)

            product_series = move_lots_by_product.get(product.id, '')

            if not product_series and bom and bom.bom_line_ids:
                all_component_series = [
                    move_lots_by_product[comp_line.product_id.id]
                    for comp_line in bom.bom_line_ids
                    if comp_line.product_id.id in move_lots_by_product
                    and move_lots_by_product[comp_line.product_id.id]
                ]
                product_series = ', '.join(all_component_series)

            data['products'].append({
                'sequence': product_sequence,
                'catalog_number': product.default_code or '',
                'product_name': product.name or '',
                'series': product_series,
                'ukt_zed': product_uktzed,
                'tax_rate': '%.0f%%' % product_tax_rate,
                'uom': order_line.product_uom.name or '',
                'quantity': product_quantity,
                'price_unit': product_price_unit,
                'price_subtotal': product_price_subtotal,
            })

            if bom and bom.bom_line_ids:
                components = []
                line_num = 0
                total_price_sum = 0.0
                total_sum = 0.0

                for bom_line in bom.bom_line_ids:
                    line_num += 1
                    component = bom_line.product_id

                    price_unit = getattr(bom_line, 'price_unit', None) or component.list_price or 0.0
                    quantity = bom_line.product_qty
                    price_subtotal = price_unit * quantity
                    total_price_sum += price_unit
                    total_sum += price_subtotal

                    tax_rate = 0.0
                    if component.taxes_id:
                        tax_rate = component.taxes_id[0].amount

                    uktzed = ''
                    if hasattr(component, 'td_uktzed_code_id') and component.td_uktzed_code_id:
                        uktzed = component.td_uktzed_code_id.code or component.td_uktzed_code_id.name or ''

                    component_series = move_lots_by_product.get(component.id, '')

                    components.append({
                        'sequence': line_num,
                        'catalog_number': component.default_code or '',
                        'product_name': component.name or '',
                        'series': component_series,
                        'ukt_zed': uktzed,
                        'tax_rate': '%.0f%%' % tax_rate,
                        'uom': bom_line.product_uom_id.name or '',
                        'quantity': quantity,
                        'price_unit': price_unit,
                        'price_subtotal': price_subtotal,
                    })

                data['documents'].append({
                    'sequence': product_sequence,
                    'catalog_number': product.default_code or '',
                    'product_name': product.name,
                    'series': product_series,
                    'ukt_zed': product_uktzed,
                    'tax_rate': '%.0f%%' % product_tax_rate,
                    'uom': order_line.product_uom.name or '',
                    'quantity': product_quantity,
                    'price_unit': product_price_unit,
                    'price_subtotal': product_price_subtotal,
                    'lines': components,
                    'total_price': total_price_sum,
                    'total': total_sum,
                })
            else:
                line_num = 1

                data['documents'].append({
                    'sequence': product_sequence,
                    'catalog_number': product.default_code or '',
                    'product_name': product.name,
                    'series': product_series,
                    'ukt_zed': product_uktzed,
                    'tax_rate': '%.0f%%' % product_tax_rate,
                    'uom': order_line.product_uom.name or '',
                    'quantity': product_quantity,
                    'price_unit': product_price_unit,
                    'price_subtotal': product_price_subtotal,
                    'lines': [{
                        'sequence': line_num,
                        'catalog_number': product.default_code or '',
                        'product_name': product.name or '',
                        'series': product_series,
                        'ukt_zed': product_uktzed,
                        'tax_rate': '%.0f%%' % product_tax_rate,
                        'uom': order_line.product_uom.name or '',
                        'quantity': product_quantity,
                        'price_unit': product_price_unit,
                        'price_subtotal': product_price_subtotal,
                    }],
                    'total': product_price_subtotal,
                })

        return data
