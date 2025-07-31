from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


class TdUomUomExchange(models.Model):
    _name = 'uom.uom'
    _inherit = ['uom.uom','ata.exchange.class']

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        return [{
            "id":     record.id,
            "name":   record.name,
            "factor": record.factor,
        } for record in self]
