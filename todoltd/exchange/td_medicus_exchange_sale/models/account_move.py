from odoo import Command, models
from markupsafe import Markup

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


class TdAccountMoveExchange(models.Model):
    _name = 'account.move'
    _inherit = ['account.move','ata.exchange.class']

    #region outgoing function
    
    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        self.ensure_one()
        methods = []

        if (self.move_type == 'out_invoice' and self.state == 'posted' and self.td_prepayment):
                methods.append(self.env.ref('td_medicus_exchange_sale.account_move_prepayment_odoo_1c'))
        
        return methods

    #при зміні Bill ставимо на обмін підпорядковані stock.picking
    def ata_exchange_add_to_queue(self):
        for record in self:
            if record.move_type == 'in_invoice' and record.state == 'posted':
                # get stock.picking
                sp_ids = self.env['stock.picking'].search([
                    ('purchase_id', 'in',
                        list(set(record.invoice_line_ids.filtered('purchase_line_id').mapped('purchase_line_id.order_id').ids)))
                ]) 
                self.env['ata.exchange.queue'].change_in_queue(sp_ids)
            else:
                super(TdAccountMoveExchange, record).ata_exchange_add_to_queue()
   
    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self,
        method: AtaExchangeMethod|None = None,
        as_node: bool = False, **kwargs) -> list[dict]|dict|str:
        
        exchange_data = []

        if method == self.env.ref('td_medicus_exchange_sale.account_move_prepayment_odoo_1c'):
            exchange_data = self.ata_exchange_get_data_prepayment(method, as_node, **kwargs)
        
        return exchange_data

    def ata_exchange_get_data_prepayment(self,
        method: AtaExchangeMethod|None = None,
        as_node: bool = False, **kwargs) -> list[dict]|dict|str:

        return [{
            "full_data":        False,
            "id":               record.id,
            "name":             record.name,
            "date":             record.invoice_date,
            **({
                "full_data":        True,
                "date_due":         record.invoice_date_due,
                "partner":          record.partner_id.exchange_data,
                "agreement":        record.td_agreement_id.exchange_data,
                "comment":          Markup(record.narration or '').striptags(),
                "warehouse_code":   (record.invoice_line_ids and
                    (sale_line_id := record.invoice_line_ids.sale_line_ids[0]) and
                    (warehouse_id := sale_line_id.order_id.warehouse_id) and
                    warehouse_id.id) or '',
                "tax":              record.invoice_line_ids and record.invoice_line_ids[0].tax_ids.exchange_data,
                "lines": [{
                    "product":      aml.product_id.exchange_data,
                    "quantity":     aml.quantity,
                    "uom":          aml.product_uom_id.exchange_data,
                    "price_unit_untaxed": aml.td_untaxed_price_unit,                
                } for aml in record.invoice_line_ids]
            } if as_node else {})
        } for record in self]

    #endregion
