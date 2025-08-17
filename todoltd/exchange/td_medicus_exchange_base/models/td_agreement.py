from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass


class TdAgreementExchange(models.Model):
    _name = 'td.agreement'
    _inherit = ['td.agreement','ata.exchange.class']

    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        methods = [
            self.env.ref('td_medicus_exchange_base.agreement_outgoing')
        ]
        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        # при обміні в складі партнера, дані по партнеру не додаємо (щоб не було рекурсії вкладень)
        return [{
            "id":           record.id,
            "name":         self._str_empty(record.name),
            "date":         self._str_empty(record.signing_date),
            "type":         record.type_of_agreement.exchange_data,
            **({
                "partner":      record.partner_id.exchange_data,
            } if not method == self.env.ref('td_medicus_exchange_base.partner_outgoing') else {}),
            "sub_client":   record.sub_client_id.exchange_data,
            "date_start":   self._str_empty(record.start_date),
            "date_end":     self._str_empty(record.end_date),
            "doc_available": False,
            "amount":       record.contract_amount,
            "budget_funds": record.budget_funds,
            "terms":        record.contract_terms,
        } for record in self]
