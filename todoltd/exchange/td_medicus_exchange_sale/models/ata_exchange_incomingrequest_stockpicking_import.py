from odoo import models
from odoo.addons.ata_exchange_v4.models.ata_exchange_base_incomingrequest_types import (
    IncomingRequestParam, IncomingResponseParam)
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler import RecordHandlerParams
from typing import cast
from .pydantic_model import StockPickingDataIncoming

class AtaExchangeIncomingrequestStockPickingImport(models.AbstractModel):
    _name = "ata.exchange.incomingrequest.stockpicking.import"
    _inherit = ["ata.exchange.base.incomingrequest", "ata.exchange.model.handler.mixin"]
    _description = "Incoming request stock picking import data from 1C 7.7"

    def ata_exchange_incomingrequest_run(self, inc_req_params: IncomingRequestParam) -> IncomingResponseParam:
        # change stock.picking import
        sp_data = cast(StockPickingDataIncoming,
            self.ata_exchange_process_data_with_pydantic(inc_req_params.req_body_data, StockPickingDataIncoming))

        sp_params = RecordHandlerParams.build_from_class(self.env, 'stock.picking', inc_req_params)
        sp_params.data = sp_data.model_dump()
        sp_params.create_record = False
        sp_params.write_record = True
        sp_params.search_params.use_matching_data = True
        sp_params.search_params.key_matching_data = 'id'
        sp_params.search_params.search_domain = [('id', '=', ext_id)] \
            if (ext_id := sp_data.ext_id) else None

        self.ata_exchange_get_model_record(sp_params)

        return sp_params.response_data
