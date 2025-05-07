from odoo import fields, models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    td_agreement_id = fields.Many2one(
                    string='Agreement', 
                    comodel_name='td.agreement', 
                    ondelete='restrict',
                    tracking=True,
                    domain='[("partner_id","=?", partner_id)]'
                    )

    def _prepare_invoice(self):
        invoice_vals = super()._prepare_invoice()
        invoice_vals['td_agreement_id'] = self.td_agreement_id.id
        return invoice_vals                