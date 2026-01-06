from odoo import _, api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    td_date_commissioning = fields.Date(
        string='Date of Commissioning',
        help='Date when the product was put into operation.',
        tracking=True
    )

    def write(self, vals):
        """Sync date_commissioning with related account.move."""
        res = super().write(vals)
        if 'td_date_commissioning' in vals:
            for picking in self:
                # Find related invoices
                if order := picking.sale_id:
                    if order.td_date_commissioning != vals['td_date_commissioning']:
                        order.td_date_commissioning = vals['td_date_commissioning']

                    invoices = self.env['account.move'].search([
                        ('invoice_origin', '=', order.name),
                        ('move_type', '=', 'out_invoice')
                    ])
                    for invoice in invoices:
                        if invoice.td_date_commissioning != vals['td_date_commissioning']:
                            invoice.sudo().write({'td_date_commissioning': vals['td_date_commissioning']})
        return res

    def _pre_action_done_hook(self):
        # Check for unlinked warranty lines before validation
        for picking in self:
            if picking.picking_type_code == 'outgoing' and picking.sale_id and picking.sale_id.td_has_warranty_products:
                unlinked_warranties = self._check_unlinked_warranties(picking.sale_id)
                if unlinked_warranties:
                    # Try to auto-link simple cases
                    auto_linked = self._auto_link_warranties(picking.sale_id, unlinked_warranties)
                    
                    # If there are still unlinked warranties, open wizard
                    if auto_linked is False:
                        return self._open_warranty_link_wizard(picking.sale_id, unlinked_warranties)

        return super()._pre_action_done_hook()

    def _action_done(self):
        """Override to create manufacturer warranties when delivery is validated."""
        
        res = super()._action_done()
        
        # Create manufacturer warranties for purchased products with serial numbers
        for picking in self:
            if picking.picking_type_code == 'incoming' and picking.location_dest_id.usage == 'internal':
                # Process each move line with a serial number
                for move_line in picking.move_line_ids:
                    if move_line.lot_id and move_line.lot_id.product_id.td_is_warranty_applicable:
                        # Create manufacturer warranty for this serial number
                        move_line.lot_id._create_manufacturer_warranty(picking)
            
            # Create extended warranties from sale order lines when delivering to customer
            elif picking.picking_type_code == 'outgoing' and picking.location_dest_id.usage == 'customer':
                if picking.sale_id and picking.sale_id.td_has_warranty_products:
                    picking.sale_id._validate_warranty_dates()
                    picking.sale_id._create_warranty_records()
        
        return res

    def _check_unlinked_warranties(self, sale_order):
        """Check if there are warranty lines without linked serial numbers."""
        warranty_lines = sale_order.order_line.filtered(lambda l: l.td_is_extended_warranty)
        unlinked = []
        
        for line in warranty_lines:
            if not line.td_warranty_linked_serial_ids:
                unlinked.append(line)
        
        return unlinked

    def _auto_link_warranties(self, sale_order, unlinked_warranties):
        """Try to automatically link warranties to serial numbers in simple cases.
        
        Returns:
            True - if all warranties were auto-linked successfully
            False - if manual linking via wizard is required
        """
        # Get all delivered serial numbers from this picking
        delivered_serials = {}
        for move_line in self.move_line_ids.filtered(lambda ml: ml.lot_id):
            product = move_line.product_id
            if product not in delivered_serials:
                delivered_serials[product] = []
            delivered_serials[product].append(move_line.lot_id)
        
        # Try to auto-link for each unlinked warranty
        for warranty_line in unlinked_warranties:
            # Find warranty-applicable products in the order (excluding warranties)
            applicable_products = sale_order.order_line.filtered(
                lambda l: not l.td_is_extended_warranty 
                and l.product_id.td_is_warranty_applicable
            )
            
            # Simple case: 1 warranty line + 1 product line with qty=1
            if len(unlinked_warranties) == 1 and len(applicable_products) == 1:
                product_line = applicable_products[0]
                if product_line.product_uom_qty == 1 and warranty_line.product_uom_qty == 1:
                    # Get serial for this product
                    serials = delivered_serials.get(product_line.product_id, [])
                    if len(serials) == 1:
                        warranty_line.td_warranty_linked_serial_ids = [(6, 0, [serials[0].id])]
                        continue
            
            # Complex case - need manual linking
            return False
        
        # All warranties were auto-linked
        return True

    def _open_warranty_link_wizard(self, sale_order, unlinked_warranties):
        """Open wizard to manually link warranties to serial numbers."""
        # Get all delivered serial numbers
        serial_ids = self.move_line_ids.filtered(lambda ml: ml.lot_id).mapped('lot_id').ids
        
        # Create wizard with lines
        wizard = self.env['td.warranty.bulk.link.wizard'].create({
            'sale_order_id': sale_order.id,
            'picking_id': self.id,
            'line_ids': [
                (0, 0, {
                    'warranty_line_id': w.id,
                    'product_id': w.product_id.id,
                    'quantity': w.product_uom_qty,
                    'available_serial_ids': [(6, 0, serial_ids)],
                }) for w in unlinked_warranties
            ],
        })
        
        return {
            'name': _('Link Warranties to Serial Numbers'),
            'type': 'ir.actions.act_window',
            'res_model': 'td.warranty.bulk.link.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
