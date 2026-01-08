from odoo import models


class TdResPartnerExchange(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner','ata.exchange.class']

    def ata_exchange_get_address_delivery(self) -> dict|str:
        self.ensure_one()

        return {
            "id":       self.id,
            "name":     self.name,
            "delivery_type": self._str_empty(self.property_delivery_carrier_id.name),
            **self.ata_exchange_get_structured_address(),
            "phone":    self._str_empty(self.phone),
            "mobile":   self._str_empty(self.mobile),
        } if self else ''
