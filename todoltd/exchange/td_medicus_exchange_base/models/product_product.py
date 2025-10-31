from odoo import api, Command, fields, models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams

from .pydantic_model import (
    ProductDataIncoming,
    ManufacturerDataIncoming,
    SupplierDataIncoming,
    SALE_TAX_MAPPING,
    PURCHASE_TAX_MAPPING
)
from typing import cast

class TdProductTemplateExchange(models.Model):
    _name = 'product.template'
    _inherit = ['product.template','ata.exchange.class']

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
            self.env.ref('td_medicus_exchange_base.product_odoo_1c')
        ]
        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False, **kwargs) -> list[dict]|dict|str:
        return [{
            "full_data":        False,
            "id":               record.id,
            "name":             record.name,
            "tracking":         self._str_empty(record.tracking),
            **({
                "full_data":   True,
                "code":             self._str_empty(record.default_code),
                "description":      self._str_empty(record.description),
                "description_sale": self._str_empty(record.description_sale),
                "type":             record.ata_exchange_get_product_type(),
                "consumable":       record.type == 'consu',                
                "category_1c_name": self._str_empty(record.td_one_c_category_id.full_name),
                # "manufacturer_name": self._str_empty(self.td_manufacturer_directory_id.name),
                "uktzed_code":      self._str_empty(self.td_uktzed_code_id.code),
                "is_landed_cost":   False,
                "catalog_code":     self._str_empty(record.default_code),
                "barcode":          self._str_empty(record.barcode),
                "price":            record.standard_price,
                "uom":              record.uom_id.exchange_data,
                "tax":              record.taxes_id.exchange_data,
            } if as_node else {}),
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

        if inc_params := record_params.incoming_params:
            if inc_params.method_id == self.env.ref('td_medicus_exchange_base.product_1c_odoo'):
                return self.ata_exchange_prepare_vals_product(record_params)

        return {}

    def ata_exchange_prepare_vals_product(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:
        
        product_data = cast(ProductDataIncoming,
            self.ata_exchange_process_data_with_pydantic(record_params.data, ProductDataIncoming))
        
        def get_category_id(category_name: str) -> int:
            category_params = record_params.build(self.env, 'td.one_c.category')
            category_params.data = {
                'full_name': category_name
            }
            category_params.create_record = True
            category_params.search_params.search_domain = [
                ('full_name', '=', category_name)
            ]
            return self.ata_exchange_get_model_record(category_params).id

        def get_seller_lines(suppliers_data: list[SupplierDataIncoming]) -> list[tuple[int,int,int]]:
            # SUPPLIERINFO
            seller_lines = []
            for supplier_data in suppliers_data:
                obj_params = record_params.build(self.env, 'res.partner',
                    self.env.ref('td_medicus_exchange_base.inner_types_product_supplier'))
                obj_params.data = supplier_data.model_dump()
                obj_params.create_record = True
                obj_params.search_params.use_matching_data = True
                obj_params.search_params.key_matching_data = 'id'
                
                partner_id = self.ata_exchange_get_model_record(obj_params).id
                seller_lines.append(Command.create({"partner_id": partner_id}))

            return [Command.clear()] + seller_lines

        def get_manufacturer_id(manufacturer_data: ManufacturerDataIncoming|None = None) -> int|bool:
            if not manufacturer_data:
                return False

            obj_params = record_params.build(self.env, 'res.partner',
                self.env.ref('td_medicus_exchange_base.inner_types_manufacturer_1c'))
            obj_params.data = manufacturer_data.model_dump()
            obj_params.create_record = True
            obj_params.search_params.use_matching_data = True
            obj_params.search_params.key_matching_data = 'id'

            return self.ata_exchange_get_model_record(obj_params).id

        def get_uktzed_id(uktzed_code: str) -> int:
            uktzed_params = record_params.build(self.env, 'td.uktzed')
            uktzed_params.search_params.search_domain = [
                ('code', '=', uktzed_code)
            ]
            return self.ata_exchange_get_model_record(uktzed_params).id
        
        vals: dict[str, str|int|list] = {
            "name":                 product_data.name,
            "description_sale":     product_data.name_full,
            "type":                 "consu",
            "is_storable":          True,
            "tracking":             "serial" if product_data.tracking_lot else "lot",
            "lot_valuated":         True,
            "default_code":         product_data.catalog_code,
            "td_one_c_category_id": get_category_id(product_data.category),
            "td_manufacturer_directory_res_id": get_manufacturer_id(product_data.manufacturer),
            "seller_ids":           get_seller_lines(product_data.suppliers),
            "td_uktzed_code_id":    get_uktzed_id(product_data.uktzed),
            "use_expiration_date":  True,
            "barcode":              product_data.barcode or '',
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
        
        return vals
    #endregion