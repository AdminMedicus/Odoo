from odoo import api, fields, models


class TdTypesOfAgreement(models.Model):
    _name = "td.agreement.types"
    _description = "Agreement types"

    @api.model
    def _unique_name_constraint(self):
        return [('name', 'unique', 'Print type names must be unique.')]

    name = fields.Char(
        string='Name',
        required=True,
        translate=True
    )
    sequence = fields.Integer()
    td_type = fields.Selection(
        string="Agreement type",
        selection=[
            ("sales", "Sales"),
            ("purchase", "Purchase"),
            ("mixed", "Mixed"),
        ],
        default="sales",        
    )
