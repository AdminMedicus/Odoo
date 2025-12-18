from odoo import api, fields, models


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
                if picking.sale_id:
                    invoices = self.env['account.move'].search([
                        ('invoice_origin', '=', picking.sale_id.name),
                        ('move_type', '=', 'out_invoice')
                    ])
                    for invoice in invoices:
                        if invoice.td_date_commissioning != vals['td_date_commissioning']:
                            invoice.sudo().write({'td_date_commissioning': vals['td_date_commissioning']})
        return res

    def _action_done(self):
        """Override to create manufacturer warranties when delivery is validated."""
        res = super()._action_done()
        
        # Create manufacturer warranties for products delivered to customers
        for picking in self:
            if picking.picking_type_code == 'outgoing' and picking.location_dest_id.usage == 'customer':
                # Process each move line with a serial number
                for move_line in picking.move_line_ids:
                    if move_line.lot_id and move_line.lot_id.product_id.td_is_warranty_applicable:
                        # Create manufacturer warranty for this serial number
                        move_line.lot_id._create_manufacturer_warranty(picking)
                
                # Create extended warranties from sale order lines
                if picking.sale_id:
                    for line in picking.sale_id.order_line:
                        if line.td_is_extended_warranty and line.td_warranty_linked_serial_id:
                            line._create_extended_warranty_record()
        
        return res
