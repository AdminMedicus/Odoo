from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams

from typing import Any, cast
from .pydantic_model import AgreementDataWithPartner, AgreementType


class TdAgreementExchange(models.Model):
    _name = 'td.agreement'
    _inherit = ['td.agreement','ata.exchange.class','ata.exchange.model.handler.mixin']

    #region outgoing function
    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        methods = [
            self.env.ref('td_medicus_exchange_base.agreement_odoo_1c')
        ]
        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        return [{
            "full_data":    False,
            "id":           record.id,
            "name":         self._str_empty(record.name),
            "date":         self._str_empty(record.signing_date),
            **({
                "full_data":    True,
                "type":         record.type_of_agreement.exchange_data,
                "partner":      record.partner_id.exchange_data,                
                "sub_client":   record.sub_client_id.exchange_data,
                "date_start":   self._str_empty(record.start_date),
                "date_end":     self._str_empty(record.end_date),
                "doc_available": record.document_available == 'yes',
                "amount":       record.contract_amount,
                "budget_funds": record.budget_funds,
                "terms":        record.contract_terms,
            } if as_node else {}),
        } for record in self]
    #endregion

    #region incoming function
    def ata_exchange_prepare_vals(self,
        record_params: RecordHandlerParams) -> dict:

        if inc_params := record_params.incoming_params:
            if inc_params.method_id == self.env.ref('td_medicus_exchange_base.agreement_1c_odoo'):
                return self.ata_exchange_prepare_vals_agreement(record_params)

        return super().ata_exchange_prepare_vals(record_params)

    def ata_exchange_prepare_vals_agreement(self,
        record_params: RecordHandlerParams) -> dict[str, Any]:

        agreement_data = cast(AgreementDataWithPartner,
            self.ata_exchange_process_data_with_pydantic(record_params.data, AgreementDataWithPartner))

        def get_type_of_agreement_id(agreement_type: AgreementType) -> int:
            agreement_type_params = record_params.build(self.env, 'td.agreement.types',
                self.env.ref('td_medicus_exchange_base.inner_types_agreement_type'))
            agreement_type_params.data = agreement_type.model_dump()
            agreement_type_params.create_record = True
            agreement_type_params.search_params.use_matching_data = True
            agreement_type_params.search_params.key_matching_data = 'id'
            agreement_type_params.search_params.search_domain_second = [('name', '=', agreement_type.name)]
            
            return self.ata_exchange_get_model_record(agreement_type_params).id

        return {
            **agreement_data.model_dump(include={
                'partner_id',
                'name',
                'agreement_number',
                'budget_funds'
            }, exclude={
                'id',
                'is_main_agreement',
                'is_custody_agreement',
                'sub_client'
            }),
            "type_of_agreement": get_type_of_agreement_id(agreement_data.type),
            "signing_date": agreement_data.date_doc,
            "start_date": agreement_data.date_start,
            "end_date": agreement_data.date_end,
            "contract_amount": agreement_data.amount,
            "contract_terms": agreement_data.terms,
            "document_available": 'yes' if agreement_data.doc_available else 'no',
            'sub_client_id': self.env['res.partner'].ata_exchange_get_sub_client_id(
                record_params, agreement_data.sub_client),
        }
    #endregion
