from odoo import _, models, fields, api, SUPERUSER_ID


class AgreementTypes(models.Model):
    _inherit = "td.agreement.types"

    # td_type = fields.Selection(
    #     ('implementation_document', 'Implementation Document')
    # )
    implementation_document = fields.Selection(
        selection=[
            ('exp_inv', 'Expenditure invoice'),
            ('act_res_st', 'Act of responsible storage'),
            ('move', 'Movement')
        ],
    )
