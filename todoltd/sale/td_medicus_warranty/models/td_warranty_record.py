from odoo import _, api, fields, models
from dateutil.relativedelta import relativedelta


class TdWarrantyRecord(models.Model):
    _name = 'td.warranty.record'
    _description = 'Warranty Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Warranty Reference',
        compute='_compute_name',
        store=True,
        tracking=True,
    )
    warranty_type = fields.Selection([
        ('manufacturer', 'Manufacturer Warranty'),
        ('extended', 'Extended Warranty')],
        default='extended',
        string='Warranty Type',
        required=True,
        readonly=True,
        tracking=True,
    )
    
    serial_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Serial Number',
        required=True,
        ondelete='cascade',
        help='Serial number associated with the warranty.',
        tracking=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        related='serial_id.product_id',
        string='Product',
        store=True,
        readonly=True,
        tracking=True,
        help='Product associated with the warranty.'
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        tracking=True,
        help='Customer who owns this warranty.'
    )
    
    # Dates
    date_start = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        help='The date when the warranty starts.'
    )
    date_end = fields.Date(
        string='End Date',
        compute='_compute_date_end',
        store=True,
        readonly=True,
        help='The date when the warranty ends.'
    )
    duration_months = fields.Integer(
        string='Duration (Months)',
        required=True,
        tracking=True,
        help='Warranty duration in months.'
    )
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired')],
        default='draft',
        string='Status',
        compute='_compute_status',
        store=True,
        tracking=True,
    )
    
    # Extended warranty specific fields
    sale_order_id = fields.Many2one(
        comodel_name='sale.order',
        string='Sale Order',
        readonly=True,
        tracking=True,
        help='Sale order through which the extended warranty was purchased.'
    )
    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Sale Order Line',
        readonly=True,
        tracking=True,
        help='Specific line in the sale order for this warranty.'
    )

    @api.depends('serial_id', 'warranty_type', 'date_start')
    def _compute_name(self):
        """Generate warranty reference name."""
        for record in self:
            warranty_type_str = dict(record._fields['warranty_type'].selection).get(record.warranty_type, '')
            if record.serial_id and record.warranty_type:
                record.name = f"{record.serial_id.name} - {warranty_type_str}"
            else:
                record.name = warranty_type_str or 'New Warranty'

    @api.depends('date_start', 'duration_months')
    def _compute_date_end(self):
        """Calculate warranty end date based on start date and duration."""
        for record in self:
            if record.date_start and record.duration_months:
                record.date_end = record.date_start + relativedelta(months=record.duration_months)
            else:
                record.date_end = False

    @api.depends('date_end')
    def _compute_status(self):
        """Determine if warranty is active or expired."""
        today = fields.Date.today()
        for record in self:
            if record.status == 'draft':
                continue
            if record.date_end:
                record.status = 'expired' if record.date_end < today else 'active'
            else:
                record.status = 'active'

    def action_set_active(self):
        """Set warranty status to active."""
        for record in self:
            record._compute_status()

    def action_set_draft(self):
        """Set warranty status to draft."""
        for record in self:
            record.status = 'draft'
