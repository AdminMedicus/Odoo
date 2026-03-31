from odoo import fields, models


class TdConfirmationBomWizard(models.TransientModel):
    _name = 'td.confirmation.bom.wizard'
    _description = 'Confirmation BOM Wizard'

    sale_order_id = fields.Many2one(
        comodel_name='sale.order'
    )

    def action_yes(self):
        self.ensure_one()
        return self.sale_order_id.open_completion_act()

    def action_no(self):
        self.ensure_one()
        return self.sale_order_id.with_context(skip_wizard=True).action_confirm()
