from odoo import models
from odoo.exceptions import UserError
from markupsafe import Markup

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams
from odoo.addons.stock.models.stock_picking import Picking
from odoo.addons.stock.models.stock_move import StockMove

from typing import cast
from .pydantic_model import (
    StockPickingDataIncoming
)


class TdStockPickingExchange(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking','ata.exchange.class','ata.exchange.model.handler.mixin']

    #region outgoing function
    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        self.ensure_one()
        methods = []

        if self.picking_type_code == 'incoming':
            if self.td_is_import:
                if (self.state == 'import' and self.purchase_id) or self.state == 'done':
                    methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_import_prepared_odoo_1c'))
            else:
                if self.state == 'done':
                    if self.purchase_id:
                        methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_odoo_1c'))
                    elif self.implementation_document == 'act_res_st' and self.return_ids:
                        methods.append(self.env.ref('td_medicus_exchange_sale.act_return_from_safekeeping_odoo_1c'))
                    elif self.implementation_document == 'exp_inv' and self.sale_id and self.return_id:
                        methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_outgoing_return_odoo_1c'))
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
            elif self.purchase_id and self.return_id:
                methods.append(self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_return_odoo_1c'))

        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        dispatch = {
            'td_medicus_exchange_sale.stock_picking_incoming_odoo_1c':        self.ata_exchange_get_data_incoming_main,
            'td_medicus_exchange_sale.stock_picking_incoming_return_odoo_1c': self.ata_exchange_get_data_outgoing_return,
            'td_medicus_exchange_sale.stock_picking_outgoing_odoo_1c':        self.ata_exchange_get_data_outgoing_main,
            'td_medicus_exchange_sale.stock_picking_outgoing_return_odoo_1c': self.ata_exchange_get_data_incoming_return,
            'td_medicus_exchange_sale.act_transfer_to_safekeeping_odoo_1c':   self.ata_exchange_get_data_outgoing_safekeeping,
            'td_medicus_exchange_sale.act_return_from_safekeeping_odoo_1c':   self.ata_exchange_get_data_incoming_safekeeping,
            'td_medicus_exchange_sale.products_relocation_odoo_1c':           self.ata_exchange_get_data_outgoing_relocation,
            'td_medicus_exchange_sale.return_products_relocation_odoo_1c':    self.ata_exchange_get_data_incoming_relocation,
            'td_medicus_exchange_sale.stock_picking_incoming_import_prepared_odoo_1c': self.ata_exchange_get_data_incoming_import_prepared,
        }

        method_xml_id = method.get_xml_id() if method else None
        if handler := (dispatch.get(method_xml_id) if method_xml_id else None):
            return handler(method, as_node, **kwargs)
        
        raise UserError("No handler found for method %s" % method_xml_id)

    def _get_manager_data(self, sp: Picking) -> list[dict]|dict|str:
        return sp.user_id.exchange_data if sp.user_id else ""

    def _get_manager_data_sale(self, sp: Picking) -> list[dict]|dict|str:
        return sp.sale_id.user_id.exchange_data if sp.sale_id and sp.sale_id.user_id else ""
    
    def ata_exchange_get_data_incoming_main(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_incoming(method, as_node, **kwargs),
            "import_prepared":    kwargs.get("import_prepared", False),
            "agreement":          record.purchase_id.td_agreement_id.exchange_data,
            "purchase_id":        record.purchase_id.id,
            "purchase_date":      self._str_empty(record.purchase_id.date_order),
            "partner_doc_number": self._str_empty(record.td_supplier_document),
            "partner_doc_date":   self._str_empty(record.td_date_supplier_document),
            "type_of_trade":      record.purchase_id.td_type_of_trade if record.purchase_id else record.td_type_of_trade,
        } for record in self]

    def ata_exchange_get_data_incoming_import_prepared(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        kwargs["import_prepared"] = True

        return self.ata_exchange_get_data_incoming_main(method, as_node, **kwargs)

    def ata_exchange_get_data_incoming_safekeeping(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        kwargs["compute_doc_id"] = True

        return [{
            **record.ata_exchange_get_data_incoming(method, as_node, **kwargs),
            "agreement": record.sale_id.td_agreement_id.exchange_data,
            "subclient": record.sale_id.sub_client_id.exchange_data,
            "manager":   self._get_manager_data(record),
        } for record in self]

    def ata_exchange_get_data_incoming_return(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_incoming(method, as_node, **kwargs),
            "sale_id":   record.sale_id.id,
            "agreement": record.sale_id.td_agreement_id.exchange_data,
            "subclient": record.sale_id.sub_client_id.exchange_data,
        } for record in self]

    def ata_exchange_get_data_incoming_relocation(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_incoming(method, as_node, **kwargs),
            "manager": self._get_manager_data_sale(record),
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

        def get_doc_id():
            if not kwargs.get("compute_doc_id", False) or not self.return_ids:
                return ""
            # Return last outgoing done stock.picking for the same sale order and implementation_document
            if last_picking := self.env['stock.picking'].search([
                ('id', 'in', self.return_ids.ids),
                ('picking_type_code', '=', 'outgoing'),
                ('implementation_document', '=', self.implementation_document),
                ('state', '=', 'done'),
            ], order='date_done desc', limit=1):
                return last_picking.id
            
            return ""

        return {
            "id":               self.id,
            "name":             self._str_empty(self.name),
            "date":             self._str_empty(self.date),
            "date_done":        self._str_empty(self.date_done),
            "date_plan":        self._str_empty(self.scheduled_date),
            "currency":         self.td_currency_id.exchange_data,
            "currency_rate":    self.td_currency_rate,
            "comment":          Markup(self.note or '').striptags(),
            "partner":          self.partner_id.exchange_data,            
            "warehouse_code":   self.location_dest_id.warehouse_id.id,
            "implementation_document": self._str_empty(self.implementation_document),
            "lines": [{
                "id":           sm.id,
                "product":      sm.product_id.exchange_data,
                "quantity":     sm.quantity,
                "uom":          sm.product_uom.exchange_data,
                "tax":          sm.td_taxes_ids.exchange_data,
                "currency_rate": sm.td_currency_rate,
                "doc_id":       get_doc_id(),
                "lots_data": [{
                    "lot":      sml.lot_id.exchange_data,
                    "quantity": sml.quantity,
                } for sml in sm.move_line_ids],
                **get_move_line_prices_dict(sm),                
            } for sm in self.move_ids]
        }
    
    def ata_exchange_get_data_outgoing_main(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_outgoing(method, as_node, **kwargs),
            "partner":          record.sale_id.partner_id.exchange_data,
            "partner_invoice":  record.sale_id.partner_invoice_id.exchange_data,
            "subclient":        record.sale_id.sub_client_id.exchange_data,
            "agreement":        record.sale_id.td_agreement_id.exchange_data,
        } for record in self]

    def ata_exchange_get_data_outgoing_safekeeping(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_outgoing(method, as_node, **kwargs),
            "partner":          record.sale_id.partner_id.exchange_data,
            "subclient":        record.sale_id.sub_client_id.exchange_data,
            "agreement":        record.sale_id.td_agreement_id.exchange_data,
            "manager":          self._get_manager_data(record),
        } for record in self]

    def ata_exchange_get_data_outgoing_return(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_outgoing(method, as_node, **kwargs),
            "purchase_id":      record.purchase_id.id,
            "partner":          record.partner_id.exchange_data,
            "agreement":        record.purchase_id.td_agreement_id.exchange_data,
            "type_of_trade":    record.purchase_id.td_type_of_trade
                if record.purchase_id else
                (record.return_id.td_type_of_trade if record.return_id else ""),
        } for record in self]

    def ata_exchange_get_data_outgoing_relocation(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_outgoing(method, as_node, **kwargs),
            "partner":          record.partner_id.exchange_data,
            "manager":          self._get_manager_data_sale(record),
        } for record in self]

    def ata_exchange_get_data_outgoing(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> dict:
        def get_move_line_prices_dict(stock_move: StockMove) -> dict:
            output_keys = ("price_unit_untaxed", "price_unit", "price_subtotal", "price_total")
            field_maps = {
                "doc": ("td_untaxed_price_unit", "price_unit", "price_subtotal", "price_total"),
                "sm":  ("td_untaxed_price_unit", "td_price_unit", "td_price_subtotal", "td_price_total"),
            }
            add_fields = {}

            if sol := stock_move.sale_line_id:
                record, fields = sol, field_maps["doc"]
                add_fields["currency_id"] = sol.currency_id.exchange_data
            elif pol := stock_move.purchase_line_id:
                record, fields = pol[:1], field_maps["doc"]
                add_fields["currency_id"] = pol[:1].currency_id.exchange_data
            else:
                record, fields = stock_move, field_maps["sm"]

            data = record.read(list(fields))[0] if record else {}
            return {k: data.get(f, 0.0) for k, f in zip(output_keys, fields)} | add_fields

        return {
            "id":               self.id,
            "name":             self._str_empty(self.name),
            "comment":          Markup(self.note or '').striptags(),
            "date":             self._str_empty(self.date),
            "date_done":        self._str_empty(self.date_done),
            "date_scheduled":   self.scheduled_date.date(),            
            "address_delivery": self.partner_id.ata_exchange_get_address_delivery(),            
            "warehouse_code":   self.location_id.warehouse_id.id,
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
            } for sm in self.move_ids]
        }

    #endregion

    #region incoming function
    def ata_exchange_prepare_vals(self,
        record_params: RecordHandlerParams) -> dict:

        if inc_params := record_params.incoming_params:
            if inc_params.method_id   == self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_import_1c_odoo'):
                return self.ata_exchange_prepare_vals_import(record_params)

        return super().ata_exchange_prepare_vals(record_params)

    def ata_exchange_prepare_vals_import(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:
        
        sp_data = cast(StockPickingDataIncoming,
            self.ata_exchange_process_data_with_pydantic(record_params.data, StockPickingDataIncoming))
        
        for line in sp_data.move_lines:
            sm_params = record_params.build(self.env, 'stock.move')
            sm_params.data = line.model_dump(include={'td_book_value'})
            sm_params.create_record = False
            sm_params.write_record = True
            sm_params.search_params.search_domain = [('id', '=', ext_id)] \
                if (ext_id := line.ext_id) else None

            self.ata_exchange_get_model_record(sm_params)

        return {}
    #endregion
