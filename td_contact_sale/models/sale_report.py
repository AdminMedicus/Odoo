import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class SaleReport(models.Model):
    _inherit = "sale.report"

    partner_region_id = fields.Many2one(
        comodel_name='td.res.country.region',
        string='Region',
    )
    partner_sub_client_id = fields.Many2one(
        comodel_name='res.partner',
        string='Sub Client',
    )

    def _select_additional_fields(self):
        additional_fields_info = super()._select_additional_fields()
        additional_fields_info.update({
            "partner_region_id": "partner.region_id",
            "partner_sub_client_id": "s.sub_client_id"
        })
        return additional_fields_info

    def _group_by_sale(self):
        group_by_sale = super()._group_by_sale()
        group_by_sale += """,
                        partner.region_id,
                        s.sub_client_id"""
        return group_by_sale
