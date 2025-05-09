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
            "partner_region_id": "rh.region_id",
            "partner_sub_client_id": "s.sub_client_id"
        })
        return additional_fields_info

    def _group_by_sale(self):
        group_by_sale = super()._group_by_sale()
        group_by_sale += """,
                        rh.region_id,
                        s.sub_client_id"""
        return group_by_sale

    def _with_sale(self):
        with_sale = super()._with_sale()
        with_sale += """
        RECURSIVE region_hierarchy AS (
            SELECT
                id AS child_id,
                id AS region_id
            FROM td_res_country_region
            UNION ALL
            SELECT
                r.id AS child_id,
                h.region_id
            FROM td_res_country_region r
            JOIN region_hierarchy h ON r.parent_region_id = h.child_id
        )
        """
        return with_sale

    def _from_sale(self):
        from_sale = super()._from_sale()
        from_sale += """
            LEFT JOIN region_hierarchy rh ON rh.child_id = partner.region_id
        """
        return from_sale
