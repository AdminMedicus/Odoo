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
                if not re.fullmatch(r"\d{12}", rec.vat):
                    raise ValidationError(
                        _("The tax identification number (VAT) "
                          "must consist of 12 digits without spaces or letters.")
                    )

    @api.constrains("company_registry")
    def _check_company_registry_edrpou(self):
        for rec in self:
            val = (rec.company_registry or "").strip()
            if not val:
                continue
            normalized = re.sub(r"[\s-]", "", val)
            if not re.fullmatch(r"(?:\d{8}|\d{10})", normalized):
                raise ValidationError(
                    _("The EDRPOU / Company ID must contain exactly 8 or 10 digits. "
                      "Examples: 12345678 or 1234567890.")
                )

    @api.depends('vat')
    def _get_report_info(self):
        """
        Заглушка для звітів Medicus, щоб не падало при виклику з партнера.
        """
        self.ensure_one()
        return {
            'name': self.name,
            'address': self.contact_address,
            'phone': self.phone,
            'email': self.email,
            # Якщо звіт захоче конкретні поля компанії, додамо їх сюди
        }
