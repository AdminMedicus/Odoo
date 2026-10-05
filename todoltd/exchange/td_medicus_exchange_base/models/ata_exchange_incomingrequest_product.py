from odoo import models
from odoo.addons.ata_exchange_v4.models.ata_exchange_base_incomingrequest_types import (
    IncomingRequestParam, IncomingResponseParam)
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler import RecordHandlerParams
from typing import cast
from .pydantic_model import ProductDataIncoming

class AtaExchangeIncomingrequestProduct(models.AbstractModel):
    _name = "ata.exchange.incomingrequest.product"
    _inherit = ["ata.exchange.base.incomingrequest", "ata.exchange.model.handler.mixin"]
    _description = "Incoming request product data from 1C 7.7"

    def ata_exchange_incomingrequest_run(self, inc_req_params: IncomingRequestParam) -> IncomingResponseParam:
        # create product
        product_data = cast(ProductDataIncoming,
            self.ata_exchange_process_data_with_pydantic(inc_req_params.req_body_data, ProductDataIncoming))

        product_params = RecordHandlerParams.build_from_class(self.env, 'product.product', inc_req_params)
        product_params.data = product_data.model_dump()
        product_params.create_record = True
        product_params.write_record = True
        product_params.search_params.use_matching_data = True
        product_params.search_params.key_matching_data = 'id'

        # The 1C object code (`id`) is the canonical product identity.  Do not
        # search by the raw Odoo database id returned as `ext_id`: stale or
        # duplicated links on the 1C side would otherwise make several 1C
        # nomenclatures overwrite the same Odoo product.  The matching table
        # and the safe compound-key fallback handle existing records.

        self.ata_exchange_get_model_record(product_params)

        return product_params.response_data
