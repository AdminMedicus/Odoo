from odoo import api, Command, fields, models
from typing import cast

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams

#region types
from enum import Enum
from pydantic import BaseModel as BaseModelPydantic

class ProductDataIncomingVendor(BaseModelPydantic):
    id: int
    name: str
    name_full: str

class TaxCodeEnum(str, Enum):
    TAX_20 = "vat20"
    TAX_14 = "vat14"
    TAX_7 = "vat7"
    TAX_0 = "vat0"
    TAX_FREE = "vat_free"
    TAX_NO = "vat_not"


class ProductDataIncoming(BaseModelPydantic):
    id: int
    name: str
    name_full: str
    tax_code: TaxCodeEnum
    category: str
    vendor: ProductDataIncomingVendor
    uktzed: str
    account_code: str
    supplier_code: str
    tracking_lot: bool

SALE_TAX_MAPPING = {
    TaxCodeEnum.TAX_20: "account.1_sale_tax_template_vat20_psbo",
    TaxCodeEnum.TAX_14: "account.1_sale_tax_template_vat14_psbo",
    TaxCodeEnum.TAX_7:  "account.1_sale_tax_template_vat7_psbo",
    TaxCodeEnum.TAX_0:  "account.1_sale_tax_template_vat0_psbo",
    TaxCodeEnum.TAX_FREE: "account.1_sale_tax_template_vat_free_psbo",
    TaxCodeEnum.TAX_NO: "account.1_sale_tax_template_vat_not_psbo",
}

PURCHASE_TAX_MAPPING = {
    TaxCodeEnum.TAX_20: "account.1_purchase_tax_template_vat20_psbo",
    TaxCodeEnum.TAX_14: "account.1_purchase_tax_template_vat14_psbo",
    TaxCodeEnum.TAX_7:  "account.1_purchase_tax_template_vat7_psbo",
    TaxCodeEnum.TAX_0:  "account.1_purchase_tax_template_vat0_psbo",
    TaxCodeEnum.TAX_FREE: "account.1_purchase_tax_template_vat_free_psbo",
    TaxCodeEnum.TAX_NO: "account.1_purchase_tax_template_vat_not_psbo",
}    
#endregion

class TdProductTemplateExchange(models.Model):
    _name = 'product.template'
    _inherit = ['product.template','ata.exchange.class']

    is_gift_sertificate = fields.Boolean(string="Is gift sertificate")
    
    def write(self, vals):
        over_write = super(TdProductTemplateExchange, self).write(vals)
        if over_write:
            for template in self:
                product_ids = self.env['product.product'].sudo().search([('product_tmpl_id', '=', template.id)])
                product_ids.ata_exchange_add_to_queue()

        return over_write


class TdProductProductExchange(models.Model):
    _name = 'product.product'
    _inherit = ['product.product','ata.exchange.class','ata.exchange.model.handler.mixin']

    #region outgoing function
    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        methods = [
            self.env.ref('td_medicus_exchange_base.product_outgoing')
        ]
        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        return [{
            "id":           record.id,
            "name":         record.name,
            "code":         self._str_empty(record.default_code),
            "description":  record.description,
            "type":         record.ata_exchange_get_product_type(),
            "consumable":   record.type == 'consu',
            "is_landed_cost": False,
            "price":        record.standard_price,
            "uom":          record.uom_id.exchange_data,            
        } for record in self]

    def ata_exchange_get_product_type(self) -> str:
        match self.type:
            case 'service':
                return 'service'
            case _:
                return 'product'

    #endregion

    #region incoming function
    def ata_exchange_prepare_vals(self,
        record_params: RecordHandlerParams) -> dict:

        if record_params['search_params']['method_id'] == self.env.ref('td_medicus_exchange_base.product_incoming'):
            return self.ata_exchange_prepare_vals_product(record_params)

        return {}

    def ata_exchange_prepare_vals_product(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:
        
        product_data = cast(ProductDataIncoming,
            self.ata_exchange_process_data_with_pydantic(record_params['data'], ProductDataIncoming))
        
        vals: dict[str, str|int|list] = {
            "name":                 product_data.name,
            "description_sale":     product_data.name_full,
            "type":                 "consu",
            "is_storable":          True,
            "tracking":             "serial" if product_data.tracking_lot else "lot",
            "lot_valuated":         True,
            "default_code":         product_data.supplier_code,
        }

        # TAXES
        tax_code = product_data.tax_code

        sale_tax_ext_id = SALE_TAX_MAPPING.get(tax_code)
        if sale_tax_ext_id:
            sale_tax_record = self.env.ref(sale_tax_ext_id, raise_if_not_found=False)
            if sale_tax_record:
                vals["taxes_id"] = [Command.set([sale_tax_record.id])]

        purchase_tax_ext_id = PURCHASE_TAX_MAPPING.get(tax_code)
        if purchase_tax_ext_id:
            purchase_tax_record = self.env.ref(purchase_tax_ext_id, raise_if_not_found=False)
            if purchase_tax_record:
                vals["supplier_taxes_id"] = [Command.set([purchase_tax_record.id])]

        # CATEGORY 1C
        vals["td_one_c_category_id"] = self.ata_exchange_get_model_record({
            **(default_params:=self.ata_exchange_get_default_record_handler_params('td.one_c.category')),
            'data': {
                'full_name': product_data.category
            },
            'create_record': True,
            'search_params': {
                **default_params['search_params'],
                'search_domain': [
                    ('full_name', '=', product_data.category)
                ]
            }
        }).id

        # SUPPLIERINFO
        # vals["seller_ids"] = [
        #     Command.clear(),
        #     Command.create({
        #         "partner_id": self.ata_exchange_get_model_record({
        #             **(default_params:=self.ata_exchange_get_default_record_handler_params('res.partner')),
        #             'data': {
        #                 'id': product_data.vendor.id,
        #                 'name': product_data.vendor.name,
        #                 'full_name': product_data.vendor.name_full,
        #             },
        #             'create_record': True,
        #             'search_params': {
        #                 **default_params['search_params'],
        #                 'use_matching_data': True,
        #                 'key_matching_data': 'id',
        #                 'ext_system_id': record_params['search_params']['ext_system_id'],
        #                 'method_id': self.env.ref('td_medicus_exchange_base.inner_types_vendor_1c'),
        #                 'search_domain_second': [
        #                     ('full_name', '=', product_data.vendor.name)
        #                 ]
        #             }
        #         }).id,
        #     })
        # ]

        #UKTZED
        vals["td_uktzed_code_id"] = self.ata_exchange_get_model_record({
            **(default_params:=self.ata_exchange_get_default_record_handler_params('td.uktzed')),
            'search_params': {
                **default_params['search_params'],
                'search_domain': [
                    ('code', '=', product_data.uktzed)
                ]
            }
        }).id

        #ACCOUNT CODE


        return vals
    #endregion