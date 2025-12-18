from odoo import _, api, fields, models
from dateutil.relativedelta import relativedelta


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    td_is_extended_warranty = fields.Boolean(
        string='Is Extended Warranty',
        related='product_template_id.td_is_extended_warranty',
        store=True,
        help='Indicates if this line is an extended warranty service.'
    )
    td_warranty_from_commissioning = fields.Boolean(
        string='Warranty starts from Commissioning Date',
        default=False,
        help='If checked, warranty start date will be taken from the commissioning date. Otherwise, you can manually set the start date.'
    )
    td_warranty_manual_start_date = fields.Date(
        string='Warranty Start Date',
        help='Manual warranty start date (used when not starting from commissioning date).'
    )
    td_warranty_linked_serial_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Linked Serial Number',
        help='Serial number to which this extended warranty is linked.'
    )
    td_show_link_product_button = fields.Boolean(
        string='Show Link Product Button',
        compute='_compute_td_show_link_product_button'
    )

    @api.depends('td_is_extended_warranty', 'order_id.order_line', 'order_id.order_line.product_id.td_is_warranty_applicable')
    def _compute_td_show_link_product_button(self):
        """Show the link button only if current line is extended warranty and SO has warranty products."""
        for line in self:
            show_button = False
            if line.td_is_extended_warranty and line.order_id:
                # Check if there are any warranty-applicable products in the order
                warranty_products = line.order_id.order_line.filtered(
                    lambda l: l.product_id.td_is_warranty_applicable and l.id != line.id
                )
                show_button = bool(warranty_products)
            line.td_show_link_product_button = show_button

    def action_link_warranty_to_serial(self):
        """Open wizard to link warranty to a serial number."""
        self.ensure_one()
        return {
            'name': _('Link Warranty to Serial Number'),
            'type': 'ir.actions.act_window',
            'res_model': 'td.warranty.link.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_line_id': self.id,
                'default_partner_id': self.order_id.partner_id.id,
            }
        }

    def _create_extended_warranty_record(self):
        """Create warranty record when order is confirmed and linked to serial."""
        self.ensure_one()
        if not self.td_is_extended_warranty or not self.td_warranty_linked_serial_id:
            return False

        # Determine start date
        if self.td_warranty_from_commissioning:
            # Get commissioning date from picking
            picking = self.order_id.picking_ids.filtered(lambda p: p.state == 'done')[:1]
            start_date = picking.td_date_commissioning if picking else fields.Date.today()
        else:
            start_date = self.td_warranty_manual_start_date or fields.Date.today()

        # Get duration from product
        duration = self.product_template_id.td_warranty_period_id.duration_months if self.product_template_id.td_warranty_period_id else 12

        # Create warranty record
        warranty_record = self.env['td.warranty.record'].create({
            'warranty_type': 'extended',
            'serial_id': self.td_warranty_linked_serial_id.id,
            'partner_id': self.order_id.partner_id.id,
            'date_start': start_date,
            'duration_months': duration,
            'sale_order_id': self.order_id.id,
            'sale_order_line_id': self.id,
        })
        
        return warranty_record

    @api.onchange('td_warranty_from_commissioning')
    def _onchange_td_warranty_from_commissioning(self):
        """Clear manual start date when using commissioning date."""
        if self.td_warranty_from_commissioning:
            self.td_warranty_manual_start_date = False
