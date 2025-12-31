from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    td_date_commissioning = fields.Date(
        string="Commissioning Date",
        help="Date of commissioning for warranty products"
    )
    td_has_warranty_products = fields.Boolean(
        string="Has Warranty Products",
        compute="_compute_td_has_warranty_products",
        store=False
    )

    @api.depends('order_line.td_is_extended_warranty')
    def _compute_td_has_warranty_products(self):
        for order in self:
            order.td_has_warranty_products = any(
                line.td_is_extended_warranty for line in order.order_line
            )

    def write(self, values):
        res = super().write(values)
        if 'td_date_commissioning' in values:
            for order in self:
                # Sync commissioning date to related pickings
                pickings = order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing'
                )
                for picking in pickings:
                    if picking.td_date_commissioning != values['td_date_commissioning']:
                        picking.sudo().write({'td_date_commissioning': values['td_date_commissioning']})

                invoices = self.invoice_ids.filtered(lambda i: i.move_type == 'out_invoice')
                for invoice in invoices:
                    if invoice.td_date_commissioning != values['td_date_commissioning']:
                        invoice.sudo().write({'td_date_commissioning': values['td_date_commissioning']})

        return res

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        date_commissioning = self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing'
        ).mapped('td_date_commissioning')
        invoice_vals["td_date_commissioning"] = date_commissioning[0] if date_commissioning else False
        return invoice_vals

    def action_confirm(self):
        """Validate warranty dates and create warranty records for warranty-only orders."""
        # Check if order contains only extended warranties
        warranty_lines = self.order_line.filtered(lambda l: l.td_is_extended_warranty)
        if warranty_lines and len(warranty_lines) == len(self.order_line):
            # This is a warranty-only order, validate dates
            self._validate_warranty_dates()
        
        res = super(SaleOrder, self).action_confirm()
        
        # Create warranty records for warranty-only orders
        if warranty_lines and len(warranty_lines) == len(self.order_line):
            self._create_warranty_records()
        
        return res

    def _validate_warranty_dates(self):
        """Validate that all required warranty dates are set."""
        errors = []
        
        for line in self.order_line.filtered(lambda l: l.td_is_extended_warranty):
            if line.td_warranty_from_commissioning:
                # Check if commissioning date is set on SO
                if not self.td_date_commissioning:
                    errors.append(
                        _("Line '%s': Commissioning date is required on Sale Order when 'Use Commissioning Date' is checked.")
                        % line.product_id.display_name
                    )
            else:
                # Check if manual start date is set on line
                if not line.td_warranty_manual_start_date:
                    errors.append(
                        _("Line '%s': Manual warranty start date is required when 'Use Commissioning Date' is not checked.")
                        % line.product_id.display_name
                    )
            
            # Check if warranty is linked to a serial number
            if not line.td_warranty_linked_serial_ids:
                errors.append(
                    _("Line '%s': Warranty must be linked to a serial number before confirmation.")
                    % line.product_id.display_name
                )
        
        if errors:
            raise UserError("\n".join(errors))

    def _create_warranty_records(self):
        """Create warranty records for all warranty lines."""
        for line in self.order_line.filtered(lambda l: l.td_is_extended_warranty):
            if line.td_warranty_linked_serial_ids:
                line._create_extended_warranty_record()
        
        return True