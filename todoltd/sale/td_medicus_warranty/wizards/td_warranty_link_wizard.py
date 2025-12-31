from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TdWarrantyLinkWizard(models.TransientModel):
    _name = 'td.warranty.link.wizard'
    _description = 'Link Warranty to Serial Number Wizard'

    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Sale Order Line',
        required=True,
        readonly=True
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        required=True,
        readonly=True
    )
    serial_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Serial Number',
        required=True,
        domain="[('id', 'in', available_serial_ids)]",
        help='Select the serial number for this warranty.'
    )
    available_serial_ids = fields.Many2many(
        comodel_name='stock.lot',
        compute='_compute_available_serial_ids',
        string='Available Serial Numbers'
    )
    filter_by_customer = fields.Boolean(
        string='Filter by Customer',
        default=True,
        help='When enabled, only shows serial numbers delivered to this customer.'
    )
    search_serial = fields.Char(
        string='Search Serial Number',
        help='Search serial number by name.'
    )

    @api.depends('partner_id', 'filter_by_customer', 'search_serial')
    def _compute_available_serial_ids(self):
        """Compute available serial numbers based on filters."""
        for wizard in self:
            # Base domain: only serial numbers (not lots) with warranty-applicable products
            domain = [
                ('product_id.tracking', '=', 'serial'),
                ('product_id.td_is_warranty_applicable', '=', True)
            ]

            # Apply customer filter if enabled
            if wizard.filter_by_customer and wizard.partner_id:
                # Find serial numbers delivered to this customer
                # Using stock moves that are done and belong to customer locations
                delivered_moves = self.env['stock.move.line'].search([
                    ('lot_id', '!=', False),
                    ('state', '=', 'done'),
                    ('location_dest_id.usage', '=', 'customer'),
                ])
                
                # Get partner from picking
                delivered_serials = self.env['stock.lot']
                for move_line in delivered_moves:
                    if move_line.picking_id and move_line.picking_id.partner_id.id == wizard.partner_id.id:
                        delivered_serials |= move_line.lot_id
                
                if delivered_serials:
                    domain.append(('id', 'in', delivered_serials.ids))
                else:
                    # No serials delivered to this customer
                    wizard.available_serial_ids = self.env['stock.lot']
                    continue

            # Apply search filter
            if wizard.search_serial:
                domain.append(('name', 'ilike', wizard.search_serial))

            # Search for available serials
            available_serials = self.env['stock.lot'].search(domain)
            wizard.available_serial_ids = available_serials

    @api.onchange('filter_by_customer', 'search_serial')
    def _onchange_filters(self):
        """Reset serial selection when filters change."""
        self.serial_id = False

    def action_link_serial(self):
        """Link selected serial number to warranty line."""
        self.ensure_one()
        
        if not self.serial_id:
            raise UserError(_('Please select a serial number.'))

        # Update sale order line with linked serial
        self.sale_order_line_id.write({
            'td_warranty_linked_serial_ids': [(6, 0, [self.serial_id.id])]
        })

        return {'type': 'ir.actions.act_window_close'}
