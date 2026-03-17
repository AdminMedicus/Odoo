from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Partner(models.Model):
    _inherit = "res.partner"

    region_id = fields.Many2one(
        comodel_name='td.res.country.region'
    )
    full_partner_name = fields.Char()
    sub_client_rel_ids = fields.One2many(
        comodel_name='td.res.partner.sub.client.rel',
        inverse_name='partner_id',
    )
    td_delivery_type = fields.Many2one(
        comodel_name='delivery.carrier',
        string='Delivery Type'
    )

    td_is_1c_partner = fields.Boolean(
        string="Imported from 1C",
        default=False,
        help="Technical flag: partner has been integrated from 1C at least once.",
    )

    td_is_counterparty_physical_person = fields.Boolean(
        string="Фізична особа контрагента",
        default=False,
        help="Сюди завантажуються пов’язані контакти з довідника Фізособи з 1С",
    )

    def _td_counterparty_person_position(self):
        return "фахівець по роботі з клієнтами"

    def _td_validate_counterparty_person_toggle(self, parent_id):
        if not parent_id:
            raise ValidationError(_(
                "The checkbox 'Фізична особа контрагента' can be enabled only for linked contacts of a counterparty."
            ))

        parent = self.env["res.partner"].browse(parent_id)
        if not parent.td_is_1c_partner:
            raise ValidationError(_(
                "You can enable 'Фізична особа контрагента' only after the counterparty was integrated from 1C."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [dict(v or {}) for v in vals_list]

        for vals in vals_list:
            if vals.get("td_is_counterparty_physical_person"):
                self._td_validate_counterparty_person_toggle(vals.get('parent_id'))
                vals["function"] = self._td_counterparty_person_position()

        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals or {})

        if "td_is_counterparty_physical_person" in vals and vals.get("td_is_counterparty_physical_person"):
            for rec in self:
                parent_id = vals.get("parent_id") or rec.parent_id.id
                rec._td_validate_counterparty_person_toggle(parent_id)

            vals["function"] = self._td_counterparty_person_position()

        return super().write(vals)

    @api.onchange('sub_client_rel_ids')
    def _onchange_sub_client_rel_ids(self):
        for partner in self:
            typical_len = len(
                partner.sub_client_rel_ids.filtered(
                    lambda res: res.is_typical
                )
            )
            if typical_len > 1:
                raise ValidationError(_(
                    "This client can have only 1 typical subclient"
                ))
