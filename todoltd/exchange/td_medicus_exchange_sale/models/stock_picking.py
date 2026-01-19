from odoo import Command, models
from markupsafe import Markup

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.stock.models.stock_move import StockMove
from odoo.addons.sale.models.sale_order import SaleOrder
from odoo.addons.purchase.models.purchase_order import PurchaseOrder


class TdStockPickingExchange(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking','ata.exchange.class']

    #region outgoing function
    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        self.ensure_one()
        methods = []

        if (self.picking_type_id.code == 'incoming' and self.state == 'done'):
            if self.purchase_id:
                methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_odoo_1c'))
            elif self.sale_id and self.implementation_document:
                methods.append(self.env.ref('td_medicus_exchange_sale.act_return_from_safekeeping_odoo_1c'))                
        elif (self.picking_type_id.code == 'outgoing' and
            self.state == 'done' and
            self.sale_id):
            if self.implementation_document == 'act_res_st':
                methods.append(self.env.ref('td_medicus_exchange_sale.act_transfer_to_safekeeping_odoo_1c'))
            else:
                methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_outgoing_odoo_1c'))

        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        exchange_data = []

        if method == self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_odoo_1c'):
            exchange_data = self.ata_exchange_get_data_stock_picking_incoming(method, as_node, **kwargs)
        elif method == self.env.ref('td_medicus_exchange_sale.act_return_from_safekeeping_odoo_1c'):            
            exchange_data = self.ata_exchange_get_data_return_from_safekeeping(method, as_node, **kwargs)
        elif (method == self.env.ref('td_medicus_exchange_sale.stock_picking_outgoing_odoo_1c') or
            method == self.env.ref('td_medicus_exchange_sale.act_transfer_to_safekeeping_odoo_1c')):
            
            exchange_data = self.ata_exchange_get_data_outgoing(method, as_node, **kwargs)
        
        return exchange_data

    def ata_exchange_get_data_return_from_safekeeping(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **self.ata_exchange_get_data_incoming(method, as_node,
                **(kwargs | {"origin": record.sale_id})),
            "subclient": record.sale_id.sub_client_id.exchange_data,
        } for record in self]

    def ata_exchange_get_data_stock_picking_incoming(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **self.ata_exchange_get_data_incoming(method, as_node,
                **(kwargs | {"origin": record.purchase_id})),
            "purchase_id":      record.purchase_id.id,
            "purchase_date":    self._str_empty(record.purchase_id.date_order),
        } for record in self]

    def ata_exchange_get_data_incoming(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> dict:
        def get_move_line_prices_dict(stock_move: StockMove) -> dict:
            default_prices = {
                "td_untaxed_price_unit": 0.0,
                "price_unit": 0.0,
                "price_subtotal": 0.0,
                "price_total": 0.0,
            }

            price_data = None
            if (pol:=stock_move.purchase_line_id) and (amls:=pol.invoice_lines):
                price_data = amls[:1].read(list(default_prices.keys()))                
            elif (sol:=stock_move.sale_line_id):
                price_data = sol.read(list(default_prices.keys()))
                
            if price_data:
                default_prices.update(price_data[0])
            
            return {
                "price_unit_untaxed": default_prices.pop("td_untaxed_price_unit"),
                **default_prices,
            }

        def get_tax_exchange_data(origin: SaleOrder|PurchaseOrder) -> list[dict]|dict|str:
            if not origin or not origin.order_line:
                return []
            if isinstance(origin, SaleOrder):
                line = origin.order_line[0]
                taxes = line.tax_id
            else:
                line = origin.order_line[0]
                taxes = line.taxes_id
            
            return taxes.exchange_data

        origin: SaleOrder|PurchaseOrder = kwargs.get("origin", self.purchase_id)
        
        return {
            "id":               self.id,
            "name":             self._str_empty(self.name),
            "date":             self._str_empty(self.date),
            "date_done":        self._str_empty(self.date_done),
            "comment":          self._str_empty(origin.name),            
            "partner":          self.partner_id.exchange_data,
            "partner_doc_number": self._str_empty(self.td_supplier_document),
            "partner_doc_date":   self._str_empty(self.td_date_supplier_document),
            "tax":              get_tax_exchange_data(origin),
            'agreement':        origin.td_agreement_id.exchange_data,
            "warehouse_code":   self.location_dest_id.warehouse_id.id,
            "implementation_document": self._str_empty(self.implementation_document),
            "lines": [{
                "product":      sm.product_id.exchange_data,
                "quantity":     sm.quantity,
                "uom":          sm.product_uom.exchange_data,
                "tax":          sm.td_taxes_ids.exchange_data,
                "lots_data": [{
                    "lot":      sml.lot_id.exchange_data,
                    "quantity": sml.quantity,
                } for sml in sm.move_line_ids],
                **get_move_line_prices_dict(sm),                
            } for sm in self.move_ids]
        }

    def ata_exchange_get_data_outgoing(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        def get_move_line_prices_dict(stock_move: StockMove) -> dict:
            default_prices = {
                "td_untaxed_price_unit": 0.0,
                "price_unit": 0.0,
                "price_subtotal": 0.0,
                "price_total": 0.0,
            }
            if (sol:=stock_move.sale_line_id):
                price_data = sol.read(list(default_prices.keys()))
                if price_data:
                    default_prices.update(price_data[0])
            
            return {
                "price_unit_untaxed": default_prices.pop("td_untaxed_price_unit"),
                **default_prices,
            }

        return [{
            "id":               record.id,
            "name":             self._str_empty(record.name),
            "comment":          Markup(record.note or '').striptags(),
            "date":             self._str_empty(record.date),
            "date_done":        self._str_empty(record.date_done),
            "date_scheduled":   record.scheduled_date.date(),
            "partner":          record.sale_id.partner_id.exchange_data,
            "partner_invoice":  record.sale_id.partner_invoice_id.exchange_data,
            "address_delivery": record.partner_id.ata_exchange_get_address_delivery(),
            "subclient":        record.sale_id.sub_client_id.exchange_data,
            "agreement":        record.sale_id.td_agreement_id.exchange_data,
            "warehouse_code":   record.location_id.warehouse_id.id,
            "tax":              record.sale_id and record.sale_id.order_line and \
                record.sale_id.order_line[0].tax_id.exchange_data,
            "lines": [{
                "product":      sm.product_id.exchange_data,
                "quantity":     sm.product_uom_qty,
                "uom":          sm.product_uom.exchange_data,
                "tax":          sm.td_taxes_ids.exchange_data,
                "lots_data": [{
                    "lot":      sml.lot_id.exchange_data,
                    "quantity": sml.quantity,
                } for sml in sm.move_line_ids],
                **get_move_line_prices_dict(sm)
            } for sm in record.move_ids]
        } for record in self]

     #endregion
