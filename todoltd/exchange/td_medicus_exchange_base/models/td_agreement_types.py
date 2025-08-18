from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


class TdAgreementTypesExchange(models.Model):
    _name = 'td.agreement.types'
    _inherit = ['td.agreement.types','ata.exchange.class']

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        return [{
            "name": self._str_empty(record.with_context(lang='uk_UA').name)
        } for record in self]
