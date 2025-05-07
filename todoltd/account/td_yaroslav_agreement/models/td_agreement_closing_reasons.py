from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TdAgreementClosingReasons(models.Model):
    _name = "td.agreement.closing.reason"
    _description = "Agreement Closing Reasons"

    name = fields.Char(string="Reason", required=True)
    description = fields.Text(string="Description")

    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            existing = self.search([("name", "=", record.name), ("id", "!=", record.id)], limit=1)
            if existing:
                raise ValidationError("The closing reason name must be unique!")
