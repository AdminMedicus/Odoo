from odoo import Command, models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


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

        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        exchange_data = []

        if method == self.env.ref('td_medicus_exchange_sale.stock_picking_incoming_odoo_1c'):
            exchange_data = self.ata_exchange_get_data_incoming(method, as_node, **kwargs)
        
        return exchange_data

    def ata_exchange_get_data_incoming(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        
        return [{
            "id":               record.id,
            "name":             self._str_empty(record.name),
            "date":             self._str_empty(record.date),
            "date_done":        self._str_empty(record.date_done),
            "purchase_id":      record.purchase_id.id,
            "purchase_date":    self._str_empty(record.purchase_id.date_order),
            "partner":          record.partner_id.exchange_data,
            "partner_doc_number": self._str_empty(record.purchase_id.partner_ref),
            "partner_doc_date":   self._str_empty(record.td_date_supplier_document),
            "tax":              record.purchase_id and record.purchase_id.order_line and \
                record.purchase_id.order_line[0].taxes_id.exchange_data,
            'agreement':        record.purchase_id.td_agreement_id.exchange_data,
            "warehouse_code":   self._str_empty(record.location_dest_id.warehouse_id),
            "implementation_document": self._str_empty(record.implementation_document),
            "lines": [{
                "product":      sm_line.product_id.exchange_data,
                "quantity":     sm_line.product_uom_qty,
                "uom":          sm_line.product_uom.exchange_data,
                "tax":          sm_line.td_taxes_ids.exchange_data,
            } for sm_line in record.move_ids]
        } for record in self]

     #endregion
