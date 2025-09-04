from odoo import _, models, fields, api, SUPERUSER_ID


class AgreementTypes(models.Model):
    _inherit = "td.agreement.types"

    td_type = fields.Selection(
        ('implementation_document', 'Implementation Document')
    )
