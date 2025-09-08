from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


class TdResUsersExchange(models.Model):
    _name = 'res.users'
    _inherit = ['res.users','ata.exchange.class']

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        return [{
            "id":   record.id,
            "name": employee.name if (employee := record.employee_id) else record.name,
            "vat":  self._str_empty(employee.identification_id),
        } for record in self]
