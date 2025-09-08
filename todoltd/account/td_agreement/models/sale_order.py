from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    td_agreement_id = fields.Many2one(
        string="Agreement",
        comodel_name="td.agreement",
        ondelete="restrict",
        domain='[("partner_id","=?", partner_id)]',
    )

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals["td_agreement_id"] = self.td_agreement_id.id
        return invoice_vals
