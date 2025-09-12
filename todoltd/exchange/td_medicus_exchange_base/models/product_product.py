from odoo import api, Command, fields, models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams

from .pydantic_model import ProductDataIncoming, SALE_TAX_MAPPING, PURCHASE_TAX_MAPPING
from typing import cast

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
            self.env.ref('td_medicus_exchange_base.product_odoo_1c')
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

        if inc_params := record_params.incoming_params:
            if inc_params.method_id == self.env.ref('td_medicus_exchange_base.product_1c_odoo'):
                return self.ata_exchange_prepare_vals_product(record_params)

        return {}

    def ata_exchange_prepare_vals_product(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:
        
        product_data = cast(ProductDataIncoming,
            self.ata_exchange_process_data_with_pydantic(record_params.data, ProductDataIncoming))
        
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
        category_params = record_params.build(self.env, 'td.one_c.category')
        category_params.data = {
            'full_name': product_data.category
        }
        category_params.create_record = True
        category_params.search_params.search_domain = [
            ('full_name', '=', product_data.category)
        ]
        vals["td_one_c_category_id"] = self.ata_exchange_get_model_record(category_params).id

        # SUPPLIERINFO
        seller_lines = []
        if vendor_data := product_data.vendor:
            vendor_params = record_params.build(self.env, 'res.partner',
                self.env.ref('td_medicus_exchange_base.inner_types_vendor_1c'))
            vendor_params.data = vendor_data.model_dump()
            vendor_params.create_record = True
            vendor_params.search_params.use_matching_data = True
            vendor_params.search_params.key_matching_data = 'id'
            
            partner_id = self.ata_exchange_get_model_record(vendor_params).id
            seller_lines.append(Command.create({"partner_id": partner_id}))

        vals["seller_ids"] = [Command.clear()] + seller_lines

        #UKTZED
        uktzed_params = record_params.build(self.env, 'td.uktzed')
        uktzed_params.search_params.search_domain = [
            ('code', '=', product_data.uktzed)
        ]
        vals["td_uktzed_code_id"] = self.ata_exchange_get_model_record(uktzed_params).id

        #ACCOUNT CODE

        return vals
    #endregion