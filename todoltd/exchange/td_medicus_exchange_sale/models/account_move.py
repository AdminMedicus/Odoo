from odoo import Command, models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


class TdStockPickingExchange(models.Model):
    _name = 'account.move'
    _inherit = ['account.move','ata.exchange.class']

    #region outgoing function
    
    #при зміні Bill ставимо на обмін підпорядковані stock.picking
    def ata_exchange_add_to_queue(self):
        for record in self:
            if record.move_type == 'in_invoice' and record.state == 'posted':
                # get stock.picking
                sp = self.env['stock.picking'].search([
                    ('purchase_id', 'in',
                        list(set(record.invoice_line_ids.filtered('purchase_line_id').mapped('purchase_line_id.order_id').ids)))
                ]) 
                self.env['ata.exchange.queue'].add_to_queue(sp)
   
     #endregion
