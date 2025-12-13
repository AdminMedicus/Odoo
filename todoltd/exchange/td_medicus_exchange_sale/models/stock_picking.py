from odoo import Command, models
from markupsafe import Markup

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.stock.models.stock_move import StockMove


class TdStockPickingExchange(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking','ata.exchange.class']

    #region outgoing function
    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        methods = []

        if (self.picking_type_id.code == 'incoming' and
            self.state == 'done' and
            self.purchase_id):
                methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_odoo_1c'))
        elif (self.picking_type_id.code == 'outgoing' and
            self.state == 'done' and
            self.sale_id):
                methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_outgoing_odoo_1c'))

        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        exchange_data = []

        if method == self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_odoo_1c'):
            exchange_data = self.ata_exchange_get_data_incoming(method, as_node, **kwargs)
        elif method == self.env.ref('td_medicus_exchange_sale.stock_picking_outgoing_odoo_1c'):
            exchange_data = self.ata_exchange_get_data_outgoing(method, as_node, **kwargs)
        
        return exchange_data

    def ata_exchange_get_data_incoming(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        def get_move_line_prices_dict(stock_move: StockMove) -> dict:
            default_prices = {
                "price_unit": 0.0,
                "price_subtotal": 0.0,
                "price_total": 0.0,
            }
            if (pol:=stock_move.purchase_line_id) and (amls:=pol.invoice_lines):
                price_data = amls[:1].read(list(default_prices.keys()))
                if price_data:
                    default_prices.update(price_data[0])
            
            return default_prices

        return [{
            "id":               record.id,
            "name":             self._str_empty(record.name),
            "date":             self._str_empty(record.date),
            "date_done":        self._str_empty(record.date_done),
            "comment":          self._str_empty(record.sale_id.name),
            "purchase_id":      record.purchase_id.id,
            "purchase_date":    self._str_empty(record.purchase_id.date_order),
            "partner":          record.partner_id.exchange_data,
            "partner_doc_number": self._str_empty(record.td_supplier_document),
            "partner_doc_date":   self._str_empty(record.td_date_supplier_document),
            "tax":              record.purchase_id and record.purchase_id.order_line and \
                record.purchase_id.order_line[0].taxes_id.exchange_data,
            'agreement':        record.purchase_id.td_agreement_id.exchange_data,
            "warehouse_code":   record.location_dest_id.warehouse_id.id,
            "implementation_document": self._str_empty(record.implementation_document),
            "lines": [{
                **{
                    "product":  sm.product_id.exchange_data,
                    "quantity": sm.product_uom_qty,
                    "uom":      sm.product_uom.exchange_data,
                },
                **get_move_line_prices_dict(sm),
                **{
                    "tax":  sm.td_taxes_ids.exchange_data,
                    "lots": [lot_id.exchange_data for lot_id in sm.lot_ids],
                }
            } for sm in record.move_ids]
        } for record in self]

    def ata_exchange_get_data_outgoing(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        def get_move_line_prices_dict(stock_move: StockMove) -> dict:
            default_prices = {
                "price_unit": 0.0,
                "price_subtotal": 0.0,
                "price_total": 0.0,
            }
            if (sol:=stock_move.sale_line_id):
                price_data = sol.read(list(default_prices.keys()))
                if price_data:
                    default_prices.update(price_data[0])
            
            return default_prices

        return [{
            "id":               record.id,
            "name":             self._str_empty(record.name),
            "comment":          Markup(record.note or '').striptags(),
            "date":             self._str_empty(record.date),
            "date_done":        self._str_empty(record.date_done),
            "date_scheduled":   record.scheduled_date.date(),
            "partner":          record.partner_id.exchange_data,
            "subclient":        record.sale_id.sub_client_id.exchange_data,
            "agreement":        record.sale_id.td_agreement_id.exchange_data,
            "warehouse_code":   record.location_id.warehouse_id.id,
            "tax":              record.sale_id and record.sale_id.order_line and \
                record.sale_id.order_line[0].tax_id.exchange_data,
            "lines": [{
                "product":  sm.product_id.exchange_data,
                "quantity": sm.product_uom_qty,
                "uom":      sm.product_uom.exchange_data,
                "tax":  sm.td_taxes_ids.exchange_data,
                "lots_data": [{
                    "lot": sml.lot_id.exchange_data,
                    "quantity": sml.quantity,
                } for sml in sm.move_line_ids],
                **get_move_line_prices_dict(sm)
            } for sm in record.move_ids]
        } for record in self]

     #endregion
