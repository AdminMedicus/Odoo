from odoo import api, fields, models
from dateutil.relativedelta import relativedelta


class StockLot(models.Model):
    _inherit = 'stock.lot'

    td_warranty_ids = fields.One2many(
        comodel_name='td.warranty.record',
        inverse_name='serial_id',
        string='Warranties',
        help='All warranties associated with this serial number.'
    )
    td_warranty_count = fields.Integer(
        string='Warranty Count',
        compute='_compute_td_warranty_count'
    )
    td_has_warranty = fields.Boolean(
        string='Has Warranty',
        related='product_id.td_is_warranty_applicable',
        store=True
    )
    td_last_delivery_partner_id = fields.Many2one(
        'res.partner',
        string='Last Delivery Partner',
        compute='_compute_td_last_delivery_partner_id',
        store=True,
        help='Partner from the last outgoing delivery'
    )

    @api.depends('td_warranty_ids')
    def _compute_td_warranty_count(self):
        """Count warranties for this serial number."""
        for lot in self:
            lot.td_warranty_count = len(lot.td_warranty_ids)

    @api.depends('product_id')
    def _compute_td_last_delivery_partner_id(self):
        """Compute last delivery partner - stored for searchability."""
        for lot in self:
            if not lot.product_id or not lot.product_id.tracking == 'serial':
                lot.td_last_delivery_partner_id = False
                continue
            
            # Find last outgoing delivery with this serial
            last_delivery = self.env['stock.picking'].search([
                ('state', '=', 'done'),
                ('picking_type_code', '=', 'outgoing'),
                ('move_line_ids.lot_id', '=', lot.id),
            ], order='date_done desc', limit=1)
            
            lot.td_last_delivery_partner_id = last_delivery.partner_id if last_delivery else False


    def _create_manufacturer_warranty(self, picking):
        """Create manufacturer warranty when product is received from supplier.
        This is called when an incoming picking is validated.
        The warranty start date is taken from the supplier document date."""
        self.ensure_one()
        
        # Check if product has warranty enabled
        if not self.product_id.td_is_warranty_applicable:
            return False

        # Check if manufacturer warranty already exists
        existing_warranty = self.env['td.warranty.record'].search([
            ('serial_id', '=', self.id),
            ('warranty_type', '=', 'manufacturer')
        ], limit=1)
        
        if existing_warranty:
            return False

        # Get warranty period from product
        warranty_period = self.product_id.td_warranty_period_id
        if not warranty_period:
            return False

        # Determine start date from incoming picking
        # Use supplier document date if available, otherwise use picking done date
        if hasattr(picking, 'td_date_supplier_document') and picking.td_date_supplier_document:
            start_date = picking.td_date_supplier_document
        else:
            start_date = picking.date_done.date() if picking.date_done else fields.Date.today()

        # Calculate end date
        end_date = start_date + relativedelta(months=warranty_period.duration_months)

        # Create manufacturer warranty (no partner yet, will be set when sold)
        warranty_record = self.env['td.warranty.record'].create({
            'warranty_type': 'manufacturer',
            'serial_id': self.id,
            'date_start': start_date,
            'date_end': end_date,
            'duration_months': warranty_period.duration_months,
        })
        
        return warranty_record

    def action_view_warranties(self):
        """Open warranties view for this serial number."""
        self.ensure_one()
        action = self.env.ref('td_medicus_warranty.action_td_warranty_record').read()[0]
        action['domain'] = [('serial_id', '=', self.id)]
        action['context'] = {
            'default_serial_id': self.id,
            'default_partner_id': self.env.context.get('partner_id', False),
        }
        return action

    def action_confirm_serial_selection(self):
        """Confirm serial number selection and link to warranty line.
        Works with multiple selected records from list view."""
        warranty_line_id = self.env.context.get('warranty_line_id')
        if not warranty_line_id:
            return {'type': 'ir.actions.act_window_close'}
        
        warranty_line = self.env['sale.order.line'].browse(warranty_line_id)
        if warranty_line.exists():
            # Get selected serials - in list view with footer button, self contains selected records
            selected_serials = self
            if selected_serials:
                # Link selected serial(s) to warranty line (replace existing)
                warranty_line.write({
                    'td_warranty_linked_serial_ids': [(6, 0, selected_serials.ids)]
                })
        
        return {'type': 'ir.actions.act_window_close'}
