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

    @api.depends('td_warranty_ids')
    def _compute_td_warranty_count(self):
        """Count warranties for this serial number."""
        for lot in self:
            lot.td_warranty_count = len(lot.td_warranty_ids)

    def _create_manufacturer_warranty(self, picking):
        """Create manufacturer warranty when product is first delivered to customer.
        This is called when a picking is validated."""
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

        # Determine start date - use commissioning date if available, otherwise delivery date
        start_date = picking.td_date_commissioning or picking.date_done.date() if picking.date_done else fields.Date.today()

        # Create manufacturer warranty
        warranty_record = self.env['td.warranty.record'].create({
            'warranty_type': 'manufacturer',
            'serial_id': self.id,
            'partner_id': picking.partner_id.id if picking.partner_id else False,
            'date_start': start_date,
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
