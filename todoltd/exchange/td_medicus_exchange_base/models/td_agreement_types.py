from odoo import models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams

from typing import Any, cast
from .pydantic_model import AgreementType


class TdAgreementTypesExchange(models.Model):
    _name = 'td.agreement.types'
    _inherit = ['td.agreement.types','ata.exchange.class','ata.exchange.model.handler.mixin']

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        return [{
            "id": record.id,
            "name": self._str_empty(record.with_context(lang='uk_UA').name),
            "imp_document": self.implementation_document
        } for record in self]

    def ata_exchange_prepare_vals(self,
        record_params: RecordHandlerParams) -> dict:

        agreement_type_data = cast(AgreementType,
            self.ata_exchange_process_data_with_pydantic(record_params.data, AgreementType))

        return {
            **agreement_type_data.model_dump(include={
                'name'
            }),
            "implementation_document": agreement_type_data.imp_document
        }
