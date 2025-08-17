from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


class TdResPartnerExchange(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner','ata.exchange.class']

    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        methods = [
            self.env.ref('td_medicus_exchange_base.partner_outgoing')
        ]
        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        return [{
            "full_data":    False,
            "id":           record.id,
            "name":         self._str_empty(record.name),
            "name_full":    self._str_empty(record.full_partner_name),
            "currency":     self._str_empty(record.property_purchase_currency_id.name),
            "vat":          self._str_empty(record.vat),
            "ref":          self._str_empty(record.ref),
            "company_registry":     self._str_empty(record.company_registry),
            "region":       self._str_empty(record.region_id.name),
            "manager":      self._str_empty(record.user_id.name),
            **({
                "full_data":   True,
                "address":  self.ata_exchange_get_structured_address(),
                "phone":    self._str_empty(record.phone),
                "mobile":   self._str_empty(record.mobile),                
                "agreement_main":       record.standard_agreement_expense_id.ata_exchange_get_data_record(method),
                "agreement_custody":    record.standard_agreement_custody_id.ata_exchange_get_data_record(method),
                "sub_clients":  [sub_client.sub_client_id.exchange_data
                    for sub_client in record.sub_client_rel_ids],
            } if as_node else {}),
        } for record in self]

    def ata_exchange_get_structured_address(self) -> dict:
        self.ensure_one()
        return {
            'street':       self.street or '',
            'street2':      self.street2 or '',
            'zip':          self.zip or '',
            'city':         self.city or '',
            'state_name':   self.state_id.name if self.state_id else '',
            'state_code':   self.state_id.code if self.state_id else '',
            'country_name': self.country_id.name if self.country_id else '',
            'country_code': self.country_id.code if self.country_id else '',
        }
