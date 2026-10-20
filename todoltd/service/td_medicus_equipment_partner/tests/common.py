# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('td_medicus_equipment_partner', 'post_install', '-at_install')
class TdEquipmentPartnerCase(TransactionCase):
    """Fixtures shared by the td_medicus_equipment_partner tests.

    The tests run on the client database, so every name and EDRPOU used here
    is prefixed or chosen so that it does not exist there.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=False))
        cls.company = cls.env.company

        # ── Users ─────────────────────────────────────────────────────
        cls.user_engineer = new_test_user(
            cls.env, login='td_ep_engineer', name='TD-EP Engineer',
            groups='helpdesk.group_helpdesk_user,stock.group_stock_user',
        )
        cls.user_manager = new_test_user(
            cls.env, login='td_ep_manager', name='TD-EP Manager',
            groups='helpdesk.group_helpdesk_manager,stock.group_stock_user',
        )

        # ── Companies and contacts ────────────────────────────────────
        Partner = cls.env['res.partner']
        cls.company_a = Partner.create({
            'name': 'TD-EP Company A', 'is_company': True, 'company_registry': '90000001',
        })
        cls.contact_a = Partner.create({
            'name': 'TD-EP Delivery A', 'type': 'delivery', 'parent_id': cls.company_a.id,
        })
        cls.company_b = Partner.create({
            'name': 'TD-EP Company B', 'is_company': True, 'company_registry': '90000002',
        })
        cls.contact_b = Partner.create({
            'name': 'TD-EP Contact B', 'type': 'contact', 'parent_id': cls.company_b.id,
        })
        cls.company_e = Partner.create({
            'name': 'TD-EP Company E', 'is_company': True, 'company_registry': '90000003',
        })
        cls.unknown_edrpou = '90000099'

        # ── Products and serial numbers ───────────────────────────────
        Product = cls.env['product.product']
        cls.product_device = Product.create({
            'name': 'TD-EP Device', 'type': 'consu', 'is_storable': True,
            'tracking': 'serial',
        })
        cls.product_device2 = Product.create({
            'name': 'TD-EP Device 2', 'type': 'consu', 'is_storable': True,
            'tracking': 'serial',
        })
        Lot = cls.env['stock.lot']
        cls.lot_l = Lot.create({
            'name': 'TD-EP-SN-001', 'product_id': cls.product_device.id,
            'company_id': cls.company.id,
        })
        cls.lot_l2 = Lot.create({
            'name': 'TD-EP-SN-002', 'product_id': cls.product_device.id,
            'company_id': cls.company.id,
        })
        cls.lot_l3 = Lot.create({
            'name': 'TD-EP-SN-003', 'product_id': cls.product_device.id,
            'company_id': cls.company.id,
        })
        cls.lot_other_product = Lot.create({
            'name': 'TD-EP-SN-101', 'product_id': cls.product_device2.id,
            'company_id': cls.company.id,
        })

        # ── Warehouse ─────────────────────────────────────────────────
        cls.warehouse = cls.env['stock.warehouse'].search(
            [('company_id', '=', cls.company.id)], limit=1)
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.customer_location = cls.env.ref('stock.stock_location_customers')

        # ── Helpdesk ──────────────────────────────────────────────────
        cls.team = cls.env['helpdesk.team'].create({
            'name': 'TD-EP Team',
            'use_product_repairs': True,
        })
        Stage = cls.env['helpdesk.stage']
        cls.stage_new = Stage.create({
            'name': 'TD-EP New', 'sequence': 1, 'team_ids': [Command.link(cls.team.id)],
        })
        cls.stage_done = Stage.create({
            'name': 'TD-EP Done', 'sequence': 99, 'fold': True,
            'team_ids': [Command.link(cls.team.id)],
        })

    # ── Helpers ───────────────────────────────────────────────────────
    @classmethod
    def _put_in_stock(cls, lot):
        cls.env['stock.quant']._update_available_quantity(
            lot.product_id, cls.stock_location, 1.0, lot_id=lot)

    @classmethod
    def _deliver(cls, lot, partner, implementation_document='exp_inv', user=None):
        """Validate an outgoing transfer of ``lot`` to ``partner``, as ``user``
        when given."""
        cls._put_in_stock(lot)
        picking = cls.env['stock.picking'].create({
            'picking_type_id': cls.warehouse.out_type_id.id,
            'location_id': cls.stock_location.id,
            'location_dest_id': cls.customer_location.id,
            'partner_id': partner.id,
            'implementation_document': implementation_document,
            'move_ids': [Command.create({
                'name': lot.product_id.display_name,
                'product_id': lot.product_id.id,
                'product_uom_qty': 1.0,
                'product_uom': lot.product_id.uom_id.id,
                'location_id': cls.stock_location.id,
                'location_dest_id': cls.customer_location.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        cls._set_lot(picking, lot)
        (picking.with_user(user) if user else picking).button_validate()
        return picking

    @classmethod
    def _return(cls, picking, lot):
        """Validate the full return of ``picking``."""
        wizard = cls.env['stock.return.picking'].with_context(
            active_id=picking.id, active_model='stock.picking',
        ).create({})
        wizard.product_return_moves.quantity = 1.0
        action = wizard.action_create_returns()
        return_picking = cls.env['stock.picking'].browse(action['res_id'])
        return_picking.action_assign()
        cls._set_lot(return_picking, lot)
        return_picking.button_validate()
        return return_picking

    @classmethod
    def _set_lot(cls, picking, lot):
        move = picking.move_ids
        if move.move_line_ids:
            move.move_line_ids.write({'lot_id': lot.id, 'quantity': 1.0})
        else:
            cls.env['stock.move.line'].create({
                'move_id': move.id,
                'picking_id': picking.id,
                'product_id': lot.product_id.id,
                'product_uom_id': lot.product_id.uom_id.id,
                'lot_id': lot.id,
                'quantity': 1.0,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
            })
        move.picked = True

    @classmethod
    def _ticket(cls, partner=None, lot=None, **vals):
        values = {
            'name': 'TD-EP ticket',
            'team_id': cls.team.id,
            'stage_id': cls.stage_new.id,
            'partner_id': partner.id if partner else False,
        }
        if lot:
            values.update({'lot_id': lot.id, 'product_id': lot.product_id.id})
        values.update(vals)
        return cls.env['helpdesk.ticket'].create(values)
