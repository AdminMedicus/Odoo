from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


class TdStockLotExchange(models.Model):
    _name = 'stock.lot'
    _inherit = ['stock.lot','ata.exchange.class']

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        return [{
            "id": record.id,
            "name": record.name,
            "expiration_date": self._str_empty(record.expiration_date),
            "uktzed_code": self._str_empty(record.td_uktzed_code_id.code),
        } for record in self]
