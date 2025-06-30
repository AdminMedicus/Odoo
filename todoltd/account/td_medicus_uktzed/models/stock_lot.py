from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class StockLot(models.Model):
    _inherit = 'stock.lot'

    td_uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed'
    )

    @api.constrains('td_uktzed_code_id')
    def _check_partner(self):
        for record in self:
            if record.td_uktzed_code_id and not record.td_uktzed_code_id.selectable:
                raise ValidationError(_("You can't select this code"))
