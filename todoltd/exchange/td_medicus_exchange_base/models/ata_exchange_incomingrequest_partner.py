from odoo import models
from odoo.addons.ata_exchange_v4.models.ata_exchange_base_incomingrequest_types import (
    IncomingRequestParam, IncomingResponseParam)
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler import RecordHandlerParams
from typing import cast
from .pydantic_model import PartnerDataWithAgreements


class AtaExchangeIncomingrequestPartner(models.AbstractModel):
    _name = "ata.exchange.incomingrequest.partner"
    _inherit = ["ata.exchange.base.incomingrequest", "ata.exchange.model.handler.mixin"]
    _description = "Incoming request partner data from 1C 7.7"

    def ata_exchange_incomingrequest_run(self, inc_req_params: IncomingRequestParam) -> IncomingResponseParam:
        # create partner
        partner_data = cast(PartnerDataWithAgreements,
            self.ata_exchange_process_data_with_pydantic(inc_req_params.req_body_data, PartnerDataWithAgreements))

        partner_params = RecordHandlerParams.build_from_class(self.env, 'res.partner', inc_req_params)
        partner_params.data = partner_data.model_dump()
        partner_params.create_record = True
        partner_params.search_params.use_matching_data = True
        partner_params.search_params.key_matching_data = 'id'
        partner_params.search_params.search_domain = [('id', '=', ext_id)] \
            if (ext_id := partner_data.ext_id) else None

        self.ata_exchange_get_model_record(partner_params)
        
        return partner_params.response_data
