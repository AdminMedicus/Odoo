import json

from odoo import api, models, _
from odoo.exceptions import ValidationError

from odoo.addons.ata_exchange_v4.models.ata_exchange_model_handler_mixin import RecordHandlerParams


class TdMedicusExchangeModelHandler(models.AbstractModel):
    """Medicus-only fallback used to restore lost 1C -> Odoo matching.

    ata_exchange_v4 stays unchanged.  We extend its handler from the Medicus
    module and run this fallback only for Medicus exchange methods after the
    standard search (explicit id / matching / secondary domain) returned
    nothing.
    """

    _inherit = "ata.exchange.model.handler"

    @staticmethod
    def _normalize(value):
        return " ".join(str(value or "").split()).casefold()

    @api.model
    def _one_or_error(self, records, external_id, reason):
        if len(records) <= 1:
            return records
        raise ValidationError(_(
            "Cannot safely restore 1C matching for %(external_id)s. "
            "%(reason)s matches several Odoo records: %(ids)s. "
            "Resolve the duplicates and repeat the exchange."
        ) % {
            "external_id": external_id,
            "reason": reason,
            "ids": ", ".join(map(str, records.ids)),
        })

    @api.model
    def _find_product_rebind(self, record_params):
        Product = record_params.model.with_context(active_test=False)
        data = record_params.data

        catalog_code = (data.get("catalog_code") or "").strip()
        incoming_name = self._normalize(data.get("name"))
        if not catalog_code or not incoming_name:
            return Product.browse()

        candidates = Product.search([("default_code", "=ilike", catalog_code)])
        candidates = candidates.filtered(
            lambda product: self._normalize(product.name) == incoming_name
        )

        if len(candidates) <= 1:
            return candidates

        incoming_full_name = self._normalize(data.get("name_full"))
        if incoming_full_name:
            by_full_name = candidates.filtered(
                lambda product: self._normalize(product.description_sale) == incoming_full_name
            )
            if len(by_full_name) == 1:
                return by_full_name
            if by_full_name:
                candidates = by_full_name

        return self._one_or_error(
            candidates,
            data.get("id", ""),
            _("Catalog code '%s'") % catalog_code,
        )

    @api.model
    def _get_product_matching_keys(self, record_params, records):
        """Return external keys already linked to the Odoo product.

        JSONB containment is intentional: unlike JSON equality it also finds
        matching rows that contain additional model keys.
        """
        if not records:
            return set()

        search_params = record_params.search_params
        if not search_params.method_id or not search_params.ext_system_id:
            return set()

        self.env.cr.execute(
            """
                SELECT key_object
                  FROM ata_exchange_matching_data
                 WHERE method_id = %s
                   AND ext_system_id = %s
                   AND COALESCE(stage, '') = %s
                   AND matching_data @> %s::jsonb
                 LIMIT 2
            """,
            (
                search_params.method_id.id,
                search_params.ext_system_id.id,
                search_params.stage or '',
                json.dumps({'product.product': records[0].id}),
            ),
        )
        return {
            key_object
            for key_object, in self.env.cr.fetchall()
        }

    @api.model
    def _product_matching_is_ambiguous(self, record_params, records):
        """Detect several 1C product ids linked to one Odoo product.

        Such many-to-one links were produced by the former catalog-code-only
        fallback.  Ignoring the ambiguous match lets the exact compound-key
        fallback reuse the right card (or create a new one) and repairs each
        matching row during the next full import.
        """
        return len(
            self._get_product_matching_keys(record_params, records)
        ) > 1

    @api.model
    def _product_is_linked_to_another_key(self, record_params, records):
        current_key = str(record_params.data.get('id') or '')
        linked_keys = {
            str(key)
            for key in self._get_product_matching_keys(
                record_params,
                records,
            )
        }
        return bool(linked_keys - {current_key})

    @api.model
    def _find_partner_rebind(self, record_params, method_xmlid):
        Partner = record_params.model.with_context(active_test=False)
        data = record_params.data
        external_id = data.get("id", "")

        if data.get("ext_id"):
            record = Partner.browse(data["ext_id"]).exists()
            if record:
                return record

        # Child contact/person: identify only inside its parent.
        parent_id = data.get("parent_id")
        if parent_id and method_xmlid == "td_medicus_exchange_base.inner_types_res_partner_person":
            name = (data.get("name") or "").strip()
            if name:
                candidates = Partner.search([
                    ("parent_id", "=", parent_id),
                    ("name", "=ilike", name),
                ])
                return self._one_or_error(candidates, external_id, _("Contact name"))

        # Delivery address: parent + street is substantially safer than name.
        if parent_id and method_xmlid == "td_medicus_exchange_base.inner_types_res_partner_address_delivery":
            street = (data.get("name") or "").strip()
            if street:
                candidates = Partner.search([
                    ("parent_id", "=", parent_id),
                    ("type", "=", "delivery"),
                    ("street", "=ilike", street),
                ])
                return self._one_or_error(candidates, external_id, _("Delivery address"))

        # Main counterparties: use strong identifiers first.
        if method_xmlid == "td_medicus_exchange_base.partner_1c_odoo":
            strong_keys = [
                ("vat", data.get("vat")),
                ("company_registry", data.get("company_registry")),
                ("ref", data.get("ref")),
            ]
            for field_name, raw_value in strong_keys:
                value = str(raw_value or "").strip()
                if not value:
                    continue
                candidates = Partner.search([
                    ("parent_id", "=", False),
                    (field_name, "=", value),
                ])
                if candidates:
                    return self._one_or_error(
                        candidates,
                        external_id,
                        _("Identifier '%s'") % field_name,
                    )

        # Manufacturer / supplier / sub-client payloads may only contain names.
        # Use exact normalized values and never pick an arbitrary duplicate.
        name = (data.get("name") or "").strip()
        full_name = (data.get("name_full") or "").strip()
        if not name and not full_name:
            return Partner.browse()

        candidates = Partner.search([("parent_id", "=", False)])

        if name:
            normalized_name = self._normalize(name)
            candidates = candidates.filtered(
                lambda partner: self._normalize(partner.name) == normalized_name
            )

        if full_name and len(candidates) > 1:
            normalized_full_name = self._normalize(full_name)
            by_full_name = candidates.filtered(
                lambda partner: self._normalize(partner.full_partner_name) == normalized_full_name
            )
            if by_full_name:
                candidates = by_full_name

        expected_category = {
            "td_medicus_exchange_base.inner_types_manufacturer_1c": "Виробник",
            "td_medicus_exchange_base.inner_types_product_supplier": "Постачальник",
        }.get(method_xmlid)
        if expected_category and len(candidates) > 1:
            by_category = candidates.filtered(
                lambda partner: expected_category in partner.category_id.mapped("name")
            )
            if by_category:
                candidates = by_category

        return self._one_or_error(candidates, external_id, _("Partner name"))

    @api.model
    def _find_agreement_rebind(self, record_params):
        Agreement = record_params.model
        data = record_params.data
        external_id = data.get("id", "")

        if data.get("ext_id"):
            record = Agreement.browse(data["ext_id"]).exists()
            if record:
                return record

        partner_id = data.get("partner_id")
        if not partner_id:
            return Agreement.browse()

        number = str(data.get("agreement_number") or "").strip()
        if number:
            candidates = Agreement.search([
                ("partner_id", "=", partner_id),
                ("agreement_number", "=", number),
            ])
            if candidates:
                return self._one_or_error(candidates, external_id, _("Agreement number"))

        name = str(data.get("name") or "").strip()
        if name:
            candidates = Agreement.search([
                ("partner_id", "=", partner_id),
                ("name", "=", name),
            ])
            return self._one_or_error(candidates, external_id, _("Agreement name"))

        return Agreement.browse()

    @api.model
    def search_records(self, record_params: RecordHandlerParams):
        records = super().search_records(record_params)
        if not record_params.search_params.use_matching_data:
            return records

        method = record_params.search_params.method_id
        if not method:
            return records

        method_xmlid = method.get_xml_id()
        if method_xmlid == "td_medicus_exchange_base.product_1c_odoo":
            if self._product_matching_is_ambiguous(record_params, records):
                raise ValidationError(_(
                    "Several 1C product ids are linked to Odoo product "
                    "%(product_id)s. Run the product matching audit/cleanup "
                    "before repeating the import."
                ) % {
                    "product_id": records[0].id,
                })
            if not records:
                records = self._find_product_rebind(record_params)
                if self._product_is_linked_to_another_key(
                    record_params,
                    records,
                ):
                    records = record_params.model.browse()
        elif not records and method_xmlid in {
            "td_medicus_exchange_base.partner_1c_odoo",
            "td_medicus_exchange_base.inner_types_manufacturer_1c",
            "td_medicus_exchange_base.inner_types_product_supplier",
            "td_medicus_exchange_base.inner_types_res_partner_person",
            "td_medicus_exchange_base.inner_types_res_partner_subclient",
            "td_medicus_exchange_base.inner_types_res_partner_address_delivery",
        }:
            records = self._find_partner_rebind(record_params, method_xmlid)
        elif not records and method_xmlid == "td_medicus_exchange_base.agreement_1c_odoo":
            # Partner import also carries agreements; rebind them too so a
            # rebuilt matching table does not duplicate contract history.
            records = self._find_agreement_rebind(record_params)

        if records:
            # Base get_records() will now update this existing record and, as a
            # consequence, save the missing matching through unmodified
            # ata_exchange_v4 logic.
            record_params.write_record = True

        return records
