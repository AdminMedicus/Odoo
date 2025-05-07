import json
from odoo import api, fields, models, _

TYPE_TRANSLATIONS = {
    "Sales contract": "Договір з покупцем",
    "Purchase contract": "Договор з постачальником",
    "Customer contract": "Договір з замовником",
    "Contractor contract": "Договір з підрядником",
    "Office contract": "Договір з іншими постачальниками(офіс)",
    "Finances contract": "Договор з фін. установами",
    "Other customers contract": "Договор з іншими покупцями",
    "Internal contract AVG": "Внутрішні договора AVG",
}

class Agreement(models.Model):
    _name = "td.agreement"
    _description = "Agreement"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # === FIELDS ===#
    name = fields.Char(
        string="Agreement name",
        required=True,
        copy=False,
        readonly=False,
        tracking=True,
        # index='trigram',
        default=lambda self: _("New"),
    )

    number = fields.Char(
        string="Agreement number",
        required=True,
        copy=False,
        readonly=False,
        tracking=True,
    )

    agreement_type = fields.Selection(
        string="Agreement type",
        selection=[
            ("sale", "Sales contract"),
            ("purchase", "Purchase contract"),
            ("customer", "Customer contract"),
            ("contractor", "Contractor contract"),
            ("office", "Office contract"),
            ("finances", "Finances contract"),
            ("other", "Other customers contract"),
            ("internal", "Internal contract AVG"),
        ],
        default="sale",
        tracking=True,
    )

    type_of_agreement = fields.Many2one(
        comodel_name = "td.agreement.types",
        string='Type of agreement',
    )

    signing_date = fields.Date(
        string="Signing date", copy=False, readonly=False, tracking=True
    )

    start_date = fields.Date(
        string="Start date", copy=False, readonly=False, tracking=True
    )

    end_date = fields.Date(string="End date", copy=False, readonly=False, tracking=True)

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self.env.company,
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Counterparty",
        required=True,
        change_default=True,
        index=True,
        tracking=True,
        domain="[('company_id', 'in', (False, company_id))]",
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency", store=True, tracking=True, ondelete="restrict"
    )

    account_id = fields.Many2one(
        comodel_name="account.account",
        store=True,
        readonly=False,
        check_company=True,
        tracking=True,
        domain=[["deprecated", "=", False]],
    )

    account_id_domain = fields.Char(
        compute="_compute_account_id_domain", readonly=True, store=False
    )

    @api.depends("type_of_agreement")
    def _compute_account_id_domain(self):
        for rec in self:
            if rec.type_of_agreement.td_type == "purchase":
                rec.account_id_domain = json.dumps(
                    [("account_type", "=", "liability_payable")]
                )
            elif rec.type_of_agreement.td_type == "sales":
                rec.account_id_domain = json.dumps(
                    [("account_type", "=", "asset_receivable")]
                )
            else:
                rec.account_id_domain = json.dumps(
                    [("account_type", "in", ["liability_payable", "asset_receivable"])]
                )

    @api.onchange("number", "signing_date")
    def _compute_agreement_name(self):
        for rec in self:
            if not rec.name and rec.number and rec.signing_date:
                rec.name = (
                    "#" + str(rec.number) + " " + rec.signing_date.strftime("%d.%m.%Y")
                )

    # cron method to fill up type_of_agreement for all agreements based on agreement_type field data
    def cron_fill_type_of_agreement(self):
        agreement_ids = self.env['td.agreement'].search([])
        cur_lang = self.env.user.lang
        # create records for td.agreement.types based on agreement_type
        key_val_dict = dict(self._fields['agreement_type'].selection)
        for key, agreement_type_val in key_val_dict.items():
            # if current cron user language is UA - use translation
            if cur_lang == 'uk_UA':
                agreement_type_val = TYPE_TRANSLATIONS[agreement_type_val]
            if agreement_type_val and agreement_type_val not in self.env['td.agreement.types'].search([]).mapped('name'):
                vals = {
                    'name': agreement_type_val
                }
                self.env['td.agreement.types'].create(vals)
        # fill up empty type_of_agreement fields
        for rec in agreement_ids:
            if not rec.type_of_agreement:
                key_val_dict = dict(self._fields['agreement_type'].selection)
                agreement_type_val = False
                for key, val in key_val_dict.items():
                    if key == rec.agreement_type:
                        agreement_type_val = val
                        break
                if cur_lang == 'uk_UA':
                    agreement_type_val = TYPE_TRANSLATIONS[agreement_type_val]
                if agreement_type_val:
                    rec.type_of_agreement = agreement_type_val
