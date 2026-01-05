from odoo import Command, models

from odoo.addons.ata_exchange_v4.models.ata_exchange_method import AtaExchangeMethod
from odoo.addons.ata_exchange_v4.models.ata_exchange_class  import AtaExchangeClass
from odoo.addons.base.models.res_partner import Partner
from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams

from typing import cast
from .pydantic_model import (
    ManufacturerDataIncoming,
    SupplierDataIncoming,
    PartnerDataBase,
    PartnerDataWithAgreements,
    AddressDeliveryData,
    ManagerDataIncoming,
    CleanInt
)

class TdResPartnerExchange(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner','ata.exchange.class','ata.exchange.model.handler.mixin']

    #region outgoing function
    def ata_exchange_compute_methods(self) -> list[AtaExchangeMethod]:
        methods = []
        self.ensure_one()
        # don't exchange contacts and employees
        if not self.parent_id and self.employees_count == 0:
            methods.append(self.env.ref('td_medicus_exchange_base.partner_odoo_1c'))

        return methods

    @AtaExchangeClass.ata_exchange_get_data_record_format()
    def ata_exchange_get_data_record(self, method: AtaExchangeMethod|None = None, as_node = False) -> list[dict]|dict|str:
        def get_job_data(record: Partner) -> dict:
            job_tuple = record.ata_exchange_get_job_contacts()
            contact = job_tuple[0] or job_tuple[1]

            return {
                "job_function": contact.function,
                "job_name": contact.name,
            } if contact else {}
                    
        return [{
            "full_data":    False,
            "id":           record.id,
            "name":         self._str_empty(record.name),
            "name_full":    self._str_empty(record.full_partner_name),
            "currency":     self._str_empty(record.property_purchase_currency_id.name),
            "vat":          self._str_empty(record.vat),
            "ref":          self._str_empty(record.ref),
            "company_registry": self._str_empty(record.company_registry),
            **({
                "full_data":   True,
                "region":   self._str_empty(record.region_id.full_name),
                "manager":  record.user_id.exchange_data,
                "address":  self.ata_exchange_get_structured_address(),
                "phone":    self._str_empty(record.phone),
                "mobile":   self._str_empty(record.mobile),                
                "agreement_main":       record.standard_agreement_expense_id.ata_exchange_get_data_record(method),
                "agreement_custody":    record.standard_agreement_custody_id.ata_exchange_get_data_record(method),
                "sub_clients": [sub_client.sub_client_id.exchange_data
                    for sub_client in record.sub_client_rel_ids],
                **get_job_data(record),
            } if as_node else {}),
        } for record in self]

    def ata_exchange_get_job_contacts(self) -> tuple[Partner | None, Partner | None]:
        """
        Get job contacts for partner.
        Returns:
            tuple[Partner | None, Partner | None]: Tuple of director and first any contact.
        """
        self.ensure_one()
        job_function_name = 'Директор'

        child_contacts = self.env['res.partner'].search([('parent_id', '=', self.id)])
        director = child_contacts.filtered(
            lambda c: c.function and c.function.strip().lower() == job_function_name.lower()
        )
        return (
            director[0] if director else None,
            child_contacts[0] if child_contacts else None
        )

    def ata_exchange_get_structured_address(self) -> dict:
        self.ensure_one()
        return {
            'street':       self.street or '',
            'street2':      self.street2 or '',
            'zip':          self.zip or '',
            'city':         self.city or '',
            'state_name':   self.state_id.name if self.state_id else '',
            'state_code':   self.state_id.code if self.state_id else '',
            'country_name': self.country_id.name if self.country_id else '',
            'country_code': self.country_id.code if self.country_id else '',
        }
    #endregion

    #region incoming function
    def ata_exchange_prepare_vals(self,
        record_params: RecordHandlerParams) -> dict:

        if inc_params := record_params.incoming_params:
            if inc_params.method_id   == self.env.ref('td_medicus_exchange_base.inner_types_manufacturer_1c'):
                return self.ata_exchange_prepare_vals_manufacturer(record_params)
            elif inc_params.method_id == self.env.ref('td_medicus_exchange_base.inner_types_product_supplier'):
                return self.ata_exchange_prepare_vals_supplier(record_params)
            elif inc_params.method_id == self.env.ref('td_medicus_exchange_base.inner_types_res_partner_subclient'):
                return self.ata_exchange_prepare_vals_subclient(record_params)            
            elif inc_params.method_id == self.env.ref('td_medicus_exchange_base.inner_types_res_partner_address_delivery'):
                return self.ata_exchange_prepare_vals_address_delivery(record_params)            
            elif inc_params.method_id == self.env.ref('td_medicus_exchange_base.partner_1c_odoo'):
                return self.ata_exchange_prepare_vals_partner(record_params)
        
        return super().ata_exchange_prepare_vals(record_params)

    def ata_exchange_get_category_id(self,
            record_params: RecordHandlerParams,
            category_name: str) -> int:
        
        category_params = record_params.build(self.env, 'res.partner.category')
        category_params.data = {'name': category_name}
        category_params.create_record = True
        category_params.search_params.search_domain = [('name', '=', category_name)]
        return self.ata_exchange_get_model_record(category_params).id

    def ata_exchange_prepare_vals_manufacturer(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:
        
        partner_data = cast(ManufacturerDataIncoming,
            self.ata_exchange_process_data_with_pydantic(record_params.data, ManufacturerDataIncoming))
        partner_category_name = "Виробник"

        return {
            "company_type":      "company",   
            "name":              partner_data.name,
            "full_partner_name": partner_data.name_full,
            "category_id":       [Command.set([self.ata_exchange_get_category_id(record_params, partner_category_name)])],
        }

    def ata_exchange_prepare_vals_supplier(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:
        
        partner_data = cast(SupplierDataIncoming,
            self.ata_exchange_process_data_with_pydantic(record_params.data, SupplierDataIncoming))
        partner_category_name = "Постачальник"
        
        return {
            "company_type":      "company",   
            "name":              partner_data.name,
            "full_partner_name": partner_data.name_full,
            "category_id":       [Command.set([self.ata_exchange_get_category_id(record_params, partner_category_name)])],
        }

    def ata_exchange_prepare_vals_subclient(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:
        
        subclient_data = cast(PartnerDataBase,
            self.ata_exchange_process_data_with_pydantic(record_params.data, PartnerDataBase))
        
        return subclient_data.model_dump(include={
            'name'
        })

    def ata_exchange_prepare_vals_address_delivery(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list|None]:
        
        def get_delivery_carrier_id(delivery_carrier_name: str) -> int:
            obj_params = record_params.build(self.env, 'delivery.carrier')
            obj_params.search_params.search_domain = [('name', '=', delivery_carrier_name)]
            return self.ata_exchange_get_model_record(obj_params).id

        partner_data = cast(AddressDeliveryData,
            self.ata_exchange_process_data_with_pydantic(record_params.data, AddressDeliveryData))
        
        return {
            'parent_id': record_params.data.get('parent_id',None),
            'company_type': 'person',
            'property_delivery_carrier_id': get_delivery_carrier_id(partner_data.type),
            'name': f"{partner_data.phone} {partner_data.time or ''}".strip(),
            'comment': partner_data.recipient or '',
            'street': partner_data.name or '',
        }

    def ata_exchange_prepare_vals_partner(self,
        record_params: RecordHandlerParams) -> dict[str, str|int|list]:

        partner_data = cast(PartnerDataWithAgreements,
            self.ata_exchange_process_data_with_pydantic(record_params.data, PartnerDataWithAgreements))

        def get_region_id(region_name: str) -> int:
            region_params = record_params.build(self.env, 'td.res.country.region')
            region_params.data = {'full_name': region_name}
            region_params.create_record = True
            region_params.search_params.search_domain = [('full_name', '=', region_name)]
            return self.ata_exchange_get_model_record(region_params).id

        def get_employee_id(manager_data: ManagerDataIncoming) -> int:
            employee_params = record_params.build(self.env, 'hr.employee')
            employee_params.data = {
                'name': manager_data.name,
                'identification_id': manager_data.vat,
            }
            employee_params.create_record = True
            employee_params.search_params.search_domain = [('identification_id', '=', manager_data.vat)]
            return self.ata_exchange_get_model_record(employee_params).id

        return {
            **partner_data.model_dump(include={
                'name',
                'vat',
                'ref',
                'company_registry',
                'phone',            
            }),
            "company_type":       "company",
            "full_partner_name":  partner_data.name_full,
            "street":             partner_data.address,    
            "region_id":          get_region_id(partner_data.region),
            "td_manager_id":      get_employee_id(partner_data.manager),
        }

    def ata_exchange_after_write(self, record_params: RecordHandlerParams):
        self.ensure_one()
        if inc_params := record_params.incoming_params:
            if inc_params.method_id == self.env.ref('td_medicus_exchange_base.partner_1c_odoo'):
                self.ata_exchange_after_write_partner(record_params)

    def ata_exchange_after_write_partner(self, record_params: RecordHandlerParams):
        partner_data = cast(PartnerDataWithAgreements,
            self.ata_exchange_process_data_with_pydantic(record_params.data, PartnerDataWithAgreements))
        
        def create_job_contact():
            job_contact = self.ata_exchange_get_job_contacts()
            if not job_contact[0] and partner_data.job_function and partner_data.job_name:
                job_contact_params = record_params.build(self.env, 'res.partner',
                    self.env.ref('td_medicus_exchange_base.inner_types_res_partner_chief'))
                job_contact_params.data = {
                    'is_company': False,
                    'parent_id': self.id,
                    'function': partner_data.job_function,
                    'name': partner_data.job_name,
                }
                job_contact_params.create_record = True
                job_contact_params.search_params.search_domain = [
                    ('parent_id', '=', self.id),
                    ('function', '=', partner_data.job_function)]
                
                self.ata_exchange_get_model_record(job_contact_params)
        
        def create_agreement():
            for agreement_data in partner_data.agreements:
                agreement_params = record_params.build(self.env, 'td.agreement',
                    self.env.ref('td_medicus_exchange_base.agreement_1c_odoo'))
                agreement_params.data = {
                    'partner_id': self.id,
                    **agreement_data.model_dump()
                }
                agreement_params.create_record = True
                agreement_params.search_params.use_matching_data = True
                agreement_params.search_params.key_matching_data = 'id'
                
                self.ata_exchange_get_model_record(agreement_params)
        
        def get_agreement_id(agreement_id: CleanInt, imp_document: str) -> int:
            agreement_params = record_params.build(self.env, 'td.agreement',
                self.env.ref('td_medicus_exchange_base.agreement_1c_odoo'))
            agreement_params.data = {
                'id': agreement_id,
            }
            agreement_params.search_params.use_matching_data = True
            agreement_params.search_params.key_matching_data = 'id'

            return self.ata_exchange_get_model_record(agreement_params, only_search=True)\
                .filtered_domain([('type_of_agreement.implementation_document', '=', imp_document)]).id

        def get_sub_client_rel_ids(sub_clients_data: list[PartnerDataBase]) -> list[tuple]:
            sub_client_lines = []
            for sub_client_data in sub_clients_data:
                sub_client_id = self.ata_exchange_get_sub_client_id(record_params, sub_client_data)
                sub_client_lines.append(Command.create({"sub_client_id": sub_client_id}))
            return [Command.clear()] + sub_client_lines

        def create_addresses_delivery():
            for address_data in partner_data.addresses_delivery:
                address_params = record_params.build(self.env, 'res.partner',
                    self.env.ref('td_medicus_exchange_base.inner_types_res_partner_address_delivery'))
                address_params.data = {
                    'parent_id': self.id,
                    **address_data.model_dump()
                }
                address_params.create_record = True
                address_params.search_params.use_matching_data = True
                address_params.search_params.key_matching_data = 'id'
                # address_params.search_params.method_id = self.env.ref('td_medicus_exchange_base.partner_1c_odoo')
                address_params.search_params.search_domain = [('id', '=', ext_id)] \
                    if (ext_id := address_data.ext_id) else None
                
                self.ata_exchange_get_model_record(address_params)

        create_job_contact()
        create_agreement()
        # set agreement, sub clients in partner
        self.write({
            'standard_agreement_expense_id': get_agreement_id(partner_data.agreement_main_id, "exp_inv"),
            'standard_agreement_custody_id': get_agreement_id(partner_data.agreement_custody_id, "act_res_st"),
            "sub_client_rel_ids": get_sub_client_rel_ids(partner_data.sub_clients),
        })
        create_addresses_delivery()

    def ata_exchange_get_sub_client_id(self, record_params: RecordHandlerParams, client_data: PartnerDataBase | None) -> int | None:
        if not client_data:
            return None
        
        client_params = record_params.build(self.env, 'res.partner',
            self.env.ref('td_medicus_exchange_base.inner_types_res_partner_subclient'))
        client_params.data = {
            'id': client_data.id,
            'is_company': True,
            'name': client_data.name,
        }
        client_params.create_record = True
        client_params.search_params.use_matching_data = True
        client_params.search_params.key_matching_data = 'id'
        client_params.search_params.method_id = self.env.ref('td_medicus_exchange_base.partner_1c_odoo')
        client_params.search_params.search_domain = [('id', '=', ext_id)] \
            if (ext_id := client_data.ext_id) else None
        
        return self.ata_exchange_get_model_record(client_params).id
    #endregion