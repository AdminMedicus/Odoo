from datetime import date, datetime
from typing import Annotated
from enum import Enum
import re

from pydantic import BaseModel as BaseModelPydantic, BeforeValidator, field_validator


def _empty_int_to_none(v):
    """Cleans string input by removing non-digit characters and handles empty/zero values."""
    cleaned_v = re.sub(r'\D', '', v) if isinstance(v, str) else v
    return cleaned_v if cleaned_v else None

def _empty_str_to_none(v):
    return None if v == "" else v

def _to_bool_validator(v):
    """Converts a string or int to a boolean. Other types are passed through."""
    if isinstance(v, str):
        return v.lower() == 'true'
    if isinstance(v, int):
        return v == 1
    return v

CleanInt = Annotated[int | None, BeforeValidator(_empty_int_to_none)]
OptionalDate = Annotated[date | None, BeforeValidator(_empty_str_to_none)]
OptionalDateTime = Annotated[datetime | None, BeforeValidator(_empty_str_to_none)]
StrBool = Annotated[bool, BeforeValidator(_to_bool_validator)]


# MANAGER
class ManagerDataIncoming(BaseModelPydantic):
    name: str
    vat: str

# PARTNER
class PartnerDataBase(BaseModelPydantic):
    id: str
    name: str
    ext_id: int | None = None

class ManufacturerDataIncoming(PartnerDataBase):
    name_full: str
    name_country: str

class SupplierDataIncoming(PartnerDataBase):
    name_full: str

class AddressDeliveryData(BaseModelPydantic):
    id: str
    name: str
    ext_id: int | None = None
    type: str
    recipient: str
    phone: str
    time: str

class ContactData(BaseModelPydantic):
    type: str
    id: int | None = None
    name: str
    function: str

class PartnerDataFull(PartnerDataBase):
    name_full: str
    vat: str
    ref: str
    company_registry: str
    address: str
    phone: str
    region: str
    manager: ManagerDataIncoming
    sub_clients: list[PartnerDataBase]
    addresses_delivery: list[AddressDeliveryData]
    contacts: list[ContactData]

class AgreementType(BaseModelPydantic):
    id: str
    name: str
    imp_document: str

class AgreementDataBase(BaseModelPydantic):
    id: str
    name: str
    ext_id: int | None = None
    agreement_number: str
    type: AgreementType
    date_doc: OptionalDate
    date_start: OptionalDate
    date_end: OptionalDate
    amount: float
    budget_funds: StrBool
    terms: str
    doc_available: bool
    is_main_agreement: StrBool
    is_custody_agreement: StrBool
    sub_client: PartnerDataBase | None

    @field_validator("sub_client", mode="before")
    @classmethod
    def validate_sub_client(cls, v):
        if v == "":
            return None
        return v

class AgreementDataWithPartner(AgreementDataBase):
    partner_id: int

class AgreementDataWithPartnerData(AgreementDataBase):
    partner: PartnerDataBase
    
class PartnerDataWithAgreements(PartnerDataFull):
    agreements: list[AgreementDataBase]
    agreement_main_id: CleanInt
    agreement_custody_id: CleanInt

# PRODUCT
class TaxCodeEnum(str, Enum):
    TAX_20 = "vat20"
    TAX_14 = "vat14"
    TAX_7 = "vat7"
    TAX_0 = "vat0"
    TAX_FREE = "vat_free"
    TAX_NO = "vat_not"

class ProductDataIncoming(BaseModelPydantic):
    id: str
    name: str
    ext_id: int | None = None
    name_full: str
    tax_code: TaxCodeEnum
    category: str
    manufacturer: ManufacturerDataIncoming | None = None
    suppliers: list[SupplierDataIncoming]
    uktzed: str
    account_code: str
    catalog_code: str
    barcode: str = ''
    tracking_lot: StrBool

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