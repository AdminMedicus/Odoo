from odoo import Command, models
from odoo.exceptions import UserError
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

        if (self.picking_type_code == 'incoming' and self.state == 'done'):
            if self.purchase_id:
                methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_odoo_1c'))
            elif self.sale_id and self.implementation_document == 'act_res_st':
                methods.append(self.env.ref('td_medicus_exchange_sale.act_return_from_safekeeping_odoo_1c'))
            elif self.implementation_document == 'move':
                methods.append(self.env.ref('td_medicus_exchange_sale.return_products_relocation_odoo_1c'))
        elif (self.picking_type_code == 'outgoing' and self.state == 'done'):
            if self.sale_id:
                if self.implementation_document == 'act_res_st':
                    methods.append(self.env.ref('td_medicus_exchange_sale.act_transfer_to_safekeeping_odoo_1c'))
                elif self.implementation_document == 'move':
                    methods.append(self.env.ref('td_medicus_exchange_sale.products_relocation_odoo_1c'))
                else:
                    methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_outgoing_odoo_1c'))

        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        dispatch = {
            'td_medicus_exchange_sale.stock_picking_incoming_odoo_1c':      self.ata_exchange_get_data_stock_picking_incoming,
            'td_medicus_exchange_sale.stock_picking_outgoing_odoo_1c':      self.ata_exchange_get_data_outgoing,
            'td_medicus_exchange_sale.act_transfer_to_safekeeping_odoo_1c': self.ata_exchange_get_data_outgoing,
            'td_medicus_exchange_sale.act_return_from_safekeeping_odoo_1c': self.ata_exchange_get_data_return_from_safekeeping,
            'td_medicus_exchange_sale.products_relocation_odoo_1c':         self.ata_exchange_get_data_outgoing,
            'td_medicus_exchange_sale.return_products_relocation_odoo_1c':  self.ata_exchange_get_data_incoming,
        }

        method_xml_id = method.get_xml_id() if method else None
        if handler := (dispatch.get(method_xml_id) if method_xml_id else None):
            return handler(method, as_node, **kwargs)
        
        raise UserError("No handler found for method %s" % method_xml_id)

    def ata_exchange_get_data_stock_picking_incoming(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **self.ata_exchange_get_data_incoming(method, as_node,
                **(kwargs | {"origin": record.purchase_id})),
            "purchase_id":        record.purchase_id.id,
            "purchase_date":      self._str_empty(record.purchase_id.date_order),
            "partner_doc_number": self._str_empty(self.td_supplier_document),
            "partner_doc_date":   self._str_empty(self.td_date_supplier_document),
        } for record in self]

    def ata_exchange_get_data_return_from_safekeeping(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **self.ata_exchange_get_data_incoming(method, as_node,
                **(kwargs | {"origin": record.sale_id})),
            "subclient": record.sale_id.sub_client_id.exchange_data,
        } for record in self]

    def ata_exchange_get_data_incoming(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> dict:
        def get_move_line_prices_dict(stock_move: StockMove) -> dict:
            output_keys = ("price_unit_untaxed", "price_unit", "price_subtotal", "price_total")
            field_maps = {
                "doc": ("td_untaxed_price_unit", "price_unit", "price_subtotal", "price_total"),
                "sm":  ("td_untaxed_price_unit", "td_price_unit", "td_price_subtotal", "td_price_total"),
            }

            if (pol := stock_move.purchase_line_id) and (amls := pol.invoice_lines):
                record, fields = amls[:1], field_maps["doc"]
            elif sol := stock_move.sale_line_id:
                record, fields = sol, field_maps["doc"]
            else:
                record, fields = stock_move, field_maps["sm"]

            data = record.read(list(fields))[0] if record else {}
            return {k: data.get(f, 0.0) for k, f in zip(output_keys, fields)}

        def get_tax_exchange_data(origin: SaleOrder|PurchaseOrder|StockMove) -> list[dict]|dict|str:
            if not origin:
                return []
            
            if isinstance(origin, SaleOrder):
                if not origin.order_line:
                    return []
                line = origin.order_line[0]
                taxes = line.tax_id
            elif isinstance(origin, PurchaseOrder):
                if not origin.order_line:
                    return []
                line = origin.order_line[0]
                taxes = line.taxes_id
            else:
                if not origin.td_taxes_ids:
                    return []
                taxes = origin.td_taxes_ids[0]
            
            return taxes.exchange_data

        origin: SaleOrder|PurchaseOrder|None = kwargs.get("origin", None)
        
        return {
            "id":               self.id,
            "name":             self._str_empty(self.name),
            "date":             self._str_empty(self.date),
            "date_done":        self._str_empty(self.date_done),
            "comment":          Markup(self.note or '').striptags(),
            "partner":          self.partner_id.exchange_data,            
            "tax":              get_tax_exchange_data(origin or self.move_ids[:1]),
            'agreement':        origin.td_agreement_id.exchange_data if origin else None,
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
            output_keys = ("price_unit_untaxed", "price_unit", "price_subtotal", "price_total")
            fields = ("td_untaxed_price_unit", "price_unit", "price_subtotal", "price_total")

            data = stock_move.sale_line_id.read(list(fields))[0] if stock_move.sale_line_id else {}
            return {k: data.get(f, 0.0) for k, f in zip(output_keys, fields)}

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
