from odoo import models
from odoo.exceptions import ValidationError

from typing import cast

from odoo.addons.ata_exchange_v4.models.ata_exchange_base_incomingrequest_types import IncomingRequestParam
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler import RecordHandlerParams

from odoo.addons.product.models.product_product import ProductProduct


class AtaExchangeIncomingrequestCashRegisterReceipt(models.AbstractModel):
    _name = "ata.exchange.incomingrequest.product"
    _inherit = ["ata.exchange.base.incomingrequest", "ata.exchange.model.handler.mixin"]
    _description = "Incoming request product data from 1C 7.7"

    def ata_exchange_incomingrequest_run(self, inc_req_params: IncomingRequestParam) -> dict:
        record_params: RecordHandlerParams = {
            **(default_params:=self.ata_exchange_get_default_record_handler_params(
                'product.product', inc_req_params)),
            'data': inc_req_params['req_body_data'],
            'create_record': True,
            'write_record': True,
            'search_params': {
                **default_params['search_params'],
                'use_matching_data': True,
                'key_matching_data': 'id'
            }
        }
        self.ata_exchange_check_record_params(record_params)

        # create product
        product_id = cast(ProductProduct,self.ata_exchange_get_model_record(record_params))
        self.env['ata.exchange.base.outgoingdata']._re_exchanged_add(product_id)

        return {
            'status': True if product_id else False
        }
