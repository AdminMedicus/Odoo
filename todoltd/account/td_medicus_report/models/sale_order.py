from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_invoice_from_delivery = fields.Boolean(
        string="Invoice from Delivery",
        help="Indicates whether the invoice should be created from the delivery order.",
        default=False,
    )

    def copy(self, default=None):
        if default is None:
            default = {}
        default.update({
            'td_invoice_from_delivery': False,
        })
        return super().copy(default=default)

    def td_get_co_data(self):
        self.ensure_one()

        data = {
            'company_info': {
                'name': self.company_id.partner_id.full_partner_name or self.company_id.name,
                'address': self.company_id.partner_id.contact_address_complete,
                'phone': self.company_id.phone,
                'registry': self.company_id.company_registry,
                'vat': self.company_id.vat,
                'sertificate_number': '35589038',
                'account_position': self.company_id.partner_id.property_account_position_id.name,
                'bank_account': self.company_id.partner_id.bank_ids[0].acc_number
                if self.company_id.partner_id.bank_ids else '',
                'bank_name': self.company_id.partner_id.bank_ids[0].bank_id.name
                if self.company_id.partner_id.bank_ids else '',
                'bank_bic': self.company_id.partner_id.bank_ids[0].bank_id.bic
                if self.company_id.partner_id.bank_ids else '',
            },
            'co_date': self.date_order.strftime('%d.%m.%Y'),
            'co_number': self.name.replace('S', ''),
            'consignee': self.partner_id.full_partner_name or self.partner_id.name,
            'co_manager': self.user_id.employee_id.td_partner_short_name or self.user_id.name,
            'co_manager_number': self.user_id.phone,
            'total': self.amount_total,
            'groups': [],
        }

        current_group = None
        line_num = 0
        
        for line in self.order_line:
            if line.display_type == 'line_section':
                current_group = {
                    'section_name': line.name,
                    'lines': []
                }
                data['groups'].append(current_group)
            elif not line.display_type:
                line_num += 1
                
                if current_group is None:
                    current_group = {
                        'section_name': '',
                        'lines': []
                    }
                    data['groups'].append(current_group)
                
                current_group['lines'].append({
                    'line_num': line_num,
                    'product_code': line.product_id.default_code or '',
                    'product_name': line.product_id.description_sale or line.product_id.name,
                    'product_uom': line.product_uom.name,
                    'product_qty': line.product_uom_qty,
                    'product_price_unit': line.td_untaxed_price_unit,
                    'product_price_subtotal': line.price_total,
                })

        return data
    