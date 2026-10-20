# -*- coding: utf-8 -*-
from odoo import models

# Implementation documents of an outgoing transfer that are a sale. An act of
# responsible storage ('act_res_st') and a movement ('move') hand the equipment
# over without selling it, the same split the 1C exchange makes.
SALE_DOCUMENTS = ('exp_inv', False)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        """AC-01, AC-02, AC-04: a validated sale delivery makes the company of
        its partner the owner of the delivered serial numbers; the return of
        that sale clears the owner again."""
        result = super()._action_done()
        self._td_update_lot_owners()
        return result

    def _td_is_sale_delivery(self):
        self.ensure_one()
        return (self.picking_type_code == 'outgoing'
                and self.implementation_document in SALE_DOCUMENTS)

    def _td_done_lots(self):
        return self.move_line_ids.filtered(
            lambda ml: ml.state == 'done' and ml.lot_id
        ).lot_id

    def _td_update_lot_owners(self):
        for picking in self:
            if picking._td_is_sale_delivery() and picking.partner_id:
                picking._td_done_lots().sudo().td_owner_id = (
                    picking.partner_id.commercial_partner_id)
            elif picking.return_id and picking.return_id._td_is_sale_delivery():
                buyer = picking.return_id.partner_id.commercial_partner_id
                picking._td_done_lots().filtered(
                    lambda lot: lot.td_owner_id == buyer
                ).sudo().td_owner_id = False
