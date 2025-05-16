from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Agreement(models.Model):
    _name = "td.agreement"
    _description = "Agreement"
    _inherit = "td.agreement"

    # === FIELDS ===#
    number = fields.Char(
        string="Agreement number",
        required=False,
        copy=False,
        readonly=False,
        tracking=True,
    )
    sub_client_id = fields.Many2one(
        comodel_name="res.partner",
    )
    allowed_sub_client_ids = fields.Many2many(
        comodel_name="res.partner",
        compute="_compute_allowed_sub_client_ids",
        readonly=True,
    )
    contract_amount = fields.Float(
        tracking=True
    )
    budget_funds = fields.Boolean(
        default=False,
    )
    pricelist_id = fields.Many2one(
        comodel_name="product.pricelist",
        tracking=True,
    )
    document_available = fields.Selection(
        selection=[
            ("yes", "Yes"),
            ("no", "No"),
        ],
        default="no",
    )
    main_contract = fields.Boolean(
        default=False,
    )
    contract_terms = fields.Selection(
        selection=[
            ("full", "Full payment"),
            ("deferred", "Deferred payment"),
        ],
        default="full",
    )
    implementation_document = fields.Selection(
        selection=[
            ('exp_inv', 'Expenditure invoice'),
            ('act_res_st', 'Act of responsible storage'),
            ('move', 'Movement')
        ]
    )

    pre_payment = fields.Float()
    pre_payment_date_to = fields.Date()
    pre_payment_sum = fields.Float()
    on_delivery = fields.Float()
    on_delivery_date_to = fields.Date()
    on_delivery_sum = fields.Float()
    split_debt = fields.Float(
        compute="_compute_split_debt",
    )
    months = fields.Integer(
        string="For how many months"
    )
    first_payment_date = fields.Date()
    regular_payment_date = fields.Date()
    regular_payment_sum = fields.Float(
        compute="_compute_regular_payment_sum",
        readonly=False
    )
    equal_parts = fields.Boolean(
        default=False,
    )

    @api.onchange('partner_id')
    def _compute_allowed_sub_client_ids(self):
        for rec in self:
            if rec.partner_id:
                rec.allowed_sub_client_ids = (
                    rec.partner_id.sub_client_rel_ids.sub_client_id.ids
                    or False
                )

    def calculate_split_debt_and_regular_payment_sum(self):
        for rec in self:
            if rec.pre_payment:
                pre_pay = rec.contract_amount * rec.pre_payment
            else:
                pre_pay = rec.pre_payment_sum

            if rec.on_delivery:
                delivery_pay = rec.contract_amount * rec.on_delivery
            else:
                delivery_pay = rec.on_delivery_sum
            rec.split_debt = rec.contract_amount - (pre_pay + delivery_pay)
            if rec.equal_parts:
                rec.regular_payment_sum = rec.split_debt / rec.months

    @api.onchange('split_debt', 'equal_parts')
    def _compute_regular_payment_sum(self):
        for rec in self:
            if rec.equal_parts:
                rec.regular_payment_sum = rec.split_debt / rec.months

    @api.onchange('pre_payment', 'pre_payment_sum',
                  'on_delivery', 'on_delivery_sum', 'contract_amount')
    def _compute_split_debt(self):
        for rec in self:
            if rec.pre_payment:
                pre_pay = rec.contract_amount * rec.pre_payment
            else:
                pre_pay = rec.pre_payment_sum

            if rec.on_delivery:
                delivery_pay = rec.contract_amount * rec.on_delivery
            else:
                delivery_pay = rec.on_delivery_sum
            rec.split_debt = rec.contract_amount - (pre_pay + delivery_pay)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for res in self:
            res.sub_client_id = False

    @api.onchange('main_contract')
    def _onchange_main_contract(self):
        for res in self:
            contracts = self.search([
                ('partner_id', '=', res.partner_id.id),
                ('main_contract', '=', True)
            ])
            if contracts:
                raise ValidationError(
                    _("You cannot make this contract the main "
                      "contract because the main contract is "
                      "already selected")
                )
