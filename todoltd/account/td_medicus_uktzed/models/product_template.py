from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    td_uktzed_code_id = fields.Many2one(
        comodel_name='td.uktzed'
    )

    @api.constrains('td_uktzed_code_id')
    def _check_partner(self):
        if not self.td_uktzed_code_id.selectable:
            raise ValidationError(_("You can't press this code"))
