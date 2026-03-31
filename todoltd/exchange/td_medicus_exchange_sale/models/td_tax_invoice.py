from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class import AtaExchangeClass


class TdTaxInvoiceExchange(models.Model):
    _name = 'td.tax.invoice'
    _inherit = ['td.tax.invoice', 'ata.exchange.class']

    #region outgoing function
    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        self.ensure_one()
        methods = []

        if self.state in ('confirm', 'confirm_finish'):
            if self.move_type == 'tax_inv':
                methods.append(self.env.ref('td_medicus_exchange_sale.tax_invoice_odoo_1c'))
            elif self.move_type == 'adj_inv':
                methods.append(self.env.ref('td_medicus_exchange_sale.adj_tax_invoice_odoo_1c'))

        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod | None = None, as_node=False, **kwargs) -> list[dict] | dict | str:
        dispatch = {
            'td_medicus_exchange_sale.tax_invoice_odoo_1c': self.ata_exchange_get_data_tax_invoice,
            'td_medicus_exchange_sale.adj_tax_invoice_odoo_1c': self.ata_exchange_get_data_adj_tax_invoice,
        }

        method_xml_id = method.get_xml_id() if method else None
        if handler := (dispatch.get(method_xml_id) if method_xml_id else None):
            return handler(method, as_node, **kwargs)

        return self.ata_exchange_get_data_tax_invoice_base(method, as_node, **kwargs)

    def ata_exchange_get_data_tax_invoice(self, method: AtaExchangeMethod | None = None, as_node=False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_tax_invoice_base(method, as_node, **kwargs),
        } for record in self]

    def ata_exchange_get_data_adj_tax_invoice(self, method: AtaExchangeMethod | None = None, as_node=False, **kwargs) -> list[dict]:
        return [{
            **record.ata_exchange_get_data_tax_invoice_base(method, as_node, **kwargs),
            "parent_tax": record.parent_id.ata_exchange_get_data_record(
                self.env.ref('td_medicus_exchange_sale.tax_invoice_odoo_1c'),
                False, **kwargs) if record.parent_id else "",
        } for record in self]

    def ata_exchange_get_data_tax_invoice_base(self, method: AtaExchangeMethod | None = None, as_node=False, **kwargs) -> dict:
        return {
            "full_data":        False,
            "id":               self.id,
            "name":             self.name,
            "date":             self._str_empty(self.accounting_date),
            **({
                "full_data":   True,
                "move_type":        self.move_type,
                "invoice_type":     self._str_empty(self.invoice_type),
                "state":            self.state,
                "budget_funds":     self.td_budget_funds,
                "narration":        self._str_empty(self.narration),
                "partner":          self.partner_id.exchange_data,
                "invoice":          self.invoice_id.ata_exchange_get_data_record(
                    self.env.ref('td_medicus_exchange_sale.account_move_prepayment_odoo_1c'),
                    False, **kwargs),
                "sale_order_id":    self._str_empty(self.sale_order_id.id),
                "tax":              self.tax_guide_id.exchange_data,
                "responsible_user": self.responsible_user_id.exchange_data,
                "totals": {
                    "price_with_out_tax": self.price_with_out_tax,
                    "price_vat":          self.price_vat,
                    "price_total":        self.price_total,
                },
                "lines": [{
                    "product":              line.product_id.exchange_data,
                    "quantity":             line.quantity,
                    "uom":                  line.product_uom_id.exchange_data,
                    "uktzed_code":          self._str_empty(line.uktzed_code_id.code),
                    "price_with_out_vat":   line.price_with_out_vat,
                    "vat_price":            round(line.vat_price, 2),
                    "sum_price_with_out_vat": line.sum_price_with_out_vat,
                    "sum_vat_price":        round(line.sum_vat_price, 2),
                    "sum_price_with_vat":   round(line.sum_price_with_vat, 2),
                    "lots":                 lots if (lots:=self.ata_exchange_get_data_tax_invoice_lots(line))
                        else [{
                            "lot":      "",
                            "quantity": line.quantity,
                        }],
                } for line in self.td_invoice_line_ids],
            } if as_node else {})
        }

    def ata_exchange_get_data_tax_invoice_lots(self, line):
        if not line.lot_ids or not self.sale_order_id:
            return []

        pickings = self.env['stock.picking'].search([
            ('sale_id', '=', self.sale_order_id.id),
            ('picking_type_code', '=', 'outgoing'),
            ('state', '=', 'done'),
        ])
        if not pickings:
            return []

        move_lines = self.env['stock.move.line'].search([
            ('picking_id', 'in', pickings.ids),
            ('lot_id', 'in', line.lot_ids.ids),
            ('product_id', '=', line.product_id.id),
        ])

        return [{
            "lot":      lot.exchange_data,
            "quantity": sum(mls.mapped('quantity')),
        } for lot, mls in move_lines.grouped('lot_id').items()]

    #endregion
