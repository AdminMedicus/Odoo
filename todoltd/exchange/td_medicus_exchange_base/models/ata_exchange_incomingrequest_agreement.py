from odoo import models
from odoo.addons.ata_exchange_v4.models.ata_exchange_base_incomingrequest_types import (
    IncomingRequestParam, IncomingResponseParam)
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler import RecordHandlerParams
from typing import cast
from .pydantic_model import AgreementDataWithPartnerData, PartnerDataBase

class AtaExchangeIncomingrequestPartner(models.AbstractModel):
    _name = "ata.exchange.incomingrequest.agreement"
    _inherit = ["ata.exchange.base.incomingrequest", "ata.exchange.model.handler.mixin"]
    _description = "Incoming request agreement data from 1C 7.7"

    def ata_exchange_incomingrequest_run(self, inc_req_params: IncomingRequestParam) -> IncomingResponseParam:
        agreement_data = cast(AgreementDataWithPartnerData,
            self.ata_exchange_process_data_with_pydantic(inc_req_params.req_body_data, AgreementDataWithPartnerData))

        agreement_params = RecordHandlerParams.build_from_class(self.env, 'td.agreement', inc_req_params)
        agreement_params.data = {
            **inc_req_params.req_body_data,
            'partner_id': self.env['res.partner'].ata_exchange_get_sub_client_id(
                agreement_params, agreement_data.partner
            ),
        }
        agreement_params.create_record = True
        agreement_params.write_record = True
        agreement_params.search_params.use_matching_data = True
        agreement_params.search_params.key_matching_data = 'id'
        agreement_params.search_params.search_domain = [('id', '=', ext_id)] \
            if (ext_id := agreement_data.ext_id) else None

        self.ata_exchange_get_model_record(agreement_params)
        
        return agreement_params.response_data
