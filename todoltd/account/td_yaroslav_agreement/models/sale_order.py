from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model_create_multi
    def create(self, vals_list):
        order = super().create(vals_list)

        # Apply discount to order lines if an agreement is selected
        if order.td_agreement_id:
            discount = order.td_agreement_id.discount
            for line in order.order_line:
                line.discount = discount if not line.discount else line.discount

        return order

    def write(self, values):
        agreement_changed = "td_agreement_id" in values
        result = super(SaleOrder, self).write(values)

        if self.td_agreement_id:
            discount = self.td_agreement_id.discount
            for line in self.order_line:
                if not line.discount or agreement_changed:
                    line.discount = discount

        return result
