import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class SaleReport(models.Model):
    _inherit = "sale.report"

    implementation_document = fields.Selection(
        selection=[
            ('exp_inv', 'Expenditure invoice'),
            ('act_res_st', 'Act of responsible storage'),
            ('move', 'Movement')
        ]
    )

    def _select_additional_fields(self):
        additional_fields_info = super()._select_additional_fields()
        additional_fields_info.update({
            "implementation_document": "s.implementation_document",
        })
        return additional_fields_info

    def _group_by_sale(self):
        group_by_sale = super()._group_by_sale()
        group_by_sale += """,
                        s.implementation_document"""
        return group_by_sale
