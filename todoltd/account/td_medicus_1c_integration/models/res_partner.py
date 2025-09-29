from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    td_manager_id = fields.Many2one(
        comodel_name='hr.employee'
    )

    company_registry = fields.Char(
        string="Code EDRPOU",
        compute='_compute_company_registry',
        store=True, readonly=False,
        help="The registry number of the company. "
             "Use it if it is different from the Tax ID. "
             "It must be unique across all partners of "
             "a same country"
    )

    ref = fields.Char(
        string='Certificate number',
        index=True
    )

    @api.constrains("vat")
    def _check_vat_is_pn(self):
        for rec in self:
            if rec.vat:
                if not re.fullmatch(r"\d{10}", rec.vat):
                    raise ValidationError(
                        _("The tax identification number (VAT) "
                          "must consist of 10 digits without spaces or letters.")
                    )

    @api.constrains("company_registry")
    def _check_company_registry_edrpou(self):
        for rec in self:
            if rec.company_registry:
                if not re.fullmatch(r"\d{8}", rec.company_registry):
                    raise ValidationError(
                        _("The EDRPOU (company ID) must consist of 8 digits.")
                    )
