from odoo import _, api, fields, models
from odoo.exceptions import UserError


class WarrantyBulkLinkWizard(models.TransientModel):
    _name = 'td.warranty.bulk.link.wizard'
    _description = 'Bulk Link Warranties to Serial Numbers'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True, readonly=True)
    picking_id = fields.Many2one('stock.picking', string='Delivery', readonly=True)
    line_ids = fields.One2many('td.warranty.bulk.link.wizard.line', 'wizard_id', string='Warranty Lines')

    def action_confirm(self):
        """Link warranties to selected serial numbers and continue with delivery validation."""
        self.ensure_one()
        
        # Validate that all warranties are linked
        for line in self.line_ids:
            if not line.serial_ids:
                raise UserError(_('Please select a serial number for warranty: %s') % line.product_id.display_name)
            
            # Link the serial to the warranty
            line.warranty_line_id.td_warranty_linked_serial_ids = [(6, 0, line.serial_ids.ids)]
        
        # Continue with picking validation
        if self.picking_id:
            return self.picking_id.button_validate()
        
        return {'type': 'ir.actions.act_window_close'}


class WarrantyBulkLinkWizardLine(models.TransientModel):
    _name = 'td.warranty.bulk.link.wizard.line'
    _description = 'Warranty Bulk Link Wizard Line'

    wizard_id = fields.Many2one(
        comodel_name='td.warranty.bulk.link.wizard',
        required=True,
        ondelete='cascade'
    )
    warranty_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Warranty Line',
        required=True,
        readonly=True
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Warranty Product',
        readonly=True
    )
    quantity = fields.Float(
        string='Quantity',
        readonly=True
    )
    serial_ids = fields.Many2many(
        comodel_name='stock.lot',
        relation='td_warranty_bulk_wizard_line_serial_rel',
        column1='wizard_line_id',
        column2='serial_id',
        string='Serial Numbers',
        required=True, 
        domain="[('id', 'in', available_serial_ids)]"
    )
    available_serial_ids = fields.Many2many(
        comodel_name='stock.lot',
        relation='td_warranty_bulk_wizard_line_available_serial_rel',
        column1='wizard_line_id',
        column2='serial_id',
        string='Available Serials'
    )
    
    # Display fields
    warranty_from_commissioning = fields.Boolean(
        related='warranty_line_id.td_warranty_from_commissioning',
        readonly=True
    )
    warranty_start_date = fields.Date(
        related='warranty_line_id.td_warranty_manual_start_date',
        readonly=True
    )
