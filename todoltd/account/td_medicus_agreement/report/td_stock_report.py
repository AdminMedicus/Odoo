import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class StockReport(models.Model):
    _name = "td.stock.report"
    _description = "Stock Report"
    _auto = False

    name = fields.Char()
    partner_id = fields.Many2one(
        comodel_name='res.partner'
    )
    move_id = fields.Many2one(
        comodel_name='stock.move'
    )
    shipping_address_id = fields.Many2one(
        comodel_name='res.partner'
    )
    sub_client_id = fields.Many2one(
        comodel_name='res.partner'
    )
    implementation_document = fields.Selection(
        selection=[
            ('exp_inv', 'Expenditure invoice'),
            ('act_res_st', 'Act of responsible storage'),
            ('move', 'Movement')
        ]
    )
    date = fields.Datetime()
    reference_id = fields.Many2one(
        comodel_name='stock.picking'
    )
    product_id = fields.Many2one(
        comodel_name='product.product'
    )
    lot_ids = fields.Many2many(
        comodel_name='stock.lot',
        related='move_id.lot_ids'
    )
    location_id = fields.Many2one(
        comodel_name='stock.location'
    )
    location_dest_id = fields.Many2one(
        comodel_name='stock.location'
    )
    qty_quantity = fields.Float()
    state = fields.Selection([
        ('draft', 'New'),
        ('waiting', 'Waiting Another Move'),
        ('confirmed', 'Waiting Availability'),
        ('partially_available', 'Partially Available'),
        ('assigned', 'Available'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ])

    def init(self):
        self.env.cr.execute("DROP VIEW IF EXISTS td_stock_report CASCADE;")
        self.env.cr.execute("""
            CREATE VIEW td_stock_report AS (
                SELECT
                    MIN(m.id) AS id,
                    sp.implementation_document AS implementation_document,
                    m.partner_id AS shipping_address_id,
                    sp.td_parent_partner_id AS partner_id,
                    sp.sub_client_id AS sub_client_id,
                    m.date AS date,
                    sp.id AS reference_id,
                    m.product_id AS product_id,
                    m.location_id AS location_id,
                    m.location_dest_id AS location_dest_id,
                    SUM(
                        CASE
                            WHEN spt.code = 'outgoing' THEN m.quantity
                            ELSE m.quantity * -1
                        END
                    ) AS qty_quantity,
                    m.state AS state,
                    COALESCE(sp.name, m.name) AS name,
                    m.id AS move_id
                FROM stock_move AS m
                LEFT JOIN stock_picking sp ON m.picking_id = sp.id
                LEFT JOIN stock_picking_type spt ON sp.picking_type_id = spt.id
                WHERE (spt.code = 'outgoing' OR spt.td_is_goods_balance_of_act_res_st = true)
                GROUP BY
                    sp.implementation_document,
                    m.partner_id,
                    sp.td_parent_partner_id,
                    sp.partner_id,
                    sp.sub_client_id,
                    m.product_id,
                    m.date,
                    sp.id,
                    m.id,
                    m.location_dest_id,
                    m.location_id,
                    m.state,
                    m.name      
            )
        """)
        # self.env.cr.execute("""
        #     CREATE VIEW td_stock_report AS (
        #         SELECT
        #             MIN(m.id) AS id,
        #             sp.implementation_document AS implementation_document,
        #             m.partner_id AS shipping_address_id,
        #             CASE
        #                 WHEN rp.parent_id IS NOT NULL THEN rp.parent_id
        #                 ELSE sp.partner_id
        #             END AS partner_id,
        #             sp.sub_client_id AS sub_client_id,
        #             m.date AS date,
        #             sp.id AS reference_id,
        #             m.product_id AS product_id,
        #             m.location_id AS location_id,
        #             m.location_dest_id AS location_dest_id,
        #             SUM(
        #                 CASE
        #                     WHEN spt.code = 'outgoing' THEN m.quantity
        #                     ELSE m.quantity * -1
        #                 END
        #             ) AS qty_quantity,
        #             m.state AS state,
        #             COALESCE(sp.name, m.name) AS name,
        #             m.id AS move_id
        #         FROM stock_move m
        #         LEFT JOIN stock_picking sp ON m.picking_id = sp.id
        #         LEFT JOIN stock_picking_type spt ON sp.picking_type_id = spt.id
        #         LEFT JOIN res_partner rp ON sp.partner_id = rp.id
        #         WHERE spt.code = 'outgoing'
        #             OR spt.td_is_goods_balance_of_act_res_st = True
        #         GROUP BY
        #             sp.implementation_document,
        #             rp.parent_id,
        #             sp.partner_id,
        #             m.partner_id,
        #             sp.sub_client_id,
        #             m.product_id,
        #             m.date,
        #             sp.id,
        #             m.id,
        #             m.location_dest_id,
        #             m.location_id,
        #             m.state,
        #             m.name
        #     )
        # """)
