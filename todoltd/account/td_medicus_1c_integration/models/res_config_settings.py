from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    td_days_for_tax_invoice_confirm = fields.Integer(
        config_parameter='td_days_for_tax_invoice_confirm'
    )
