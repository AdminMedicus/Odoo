# Architecture: td_medicus_equipment_partner
Methodology: tdd — thin architecture
Generated from SPEC.md v18.0.1.0.0 — 2026-10-19

## File structure

Only what the module needs to install, plus `tests/`. Views and other files are added when an AC
needs them.

```
td_medicus_equipment_partner/
├── __init__.py                 # models, controllers, post_init_hook
├── __manifest__.py
├── hooks.py                    # post_init_hook → backfills (AC-05, AC-10, AC-37)
├── pyrightconfig.json
├── SPEC.md
├── ARCHITECTURE.md
├── controllers/
│   ├── __init__.py
│   └── website_form.py         # WebsiteFormEquipment(WebsiteFormAutofill)
├── models/
│   ├── __init__.py
│   ├── stock_lot.py
│   ├── stock_picking.py
│   ├── helpdesk_ticket.py
│   ├── td_equipment_applicant.py
│   ├── td_service_report.py
│   ├── td_agreement.py
│   └── res_partner.py
├── security/
│   └── ir.model.access.csv
├── views/                      # added per AC (ticket, lot, report, applicant, menus)
└── tests/
    ├── __init__.py
    ├── common.py
    ├── test_lot_owner.py
    ├── test_ticket_equipment.py
    ├── test_ticket_owner.py
    ├── test_website_form.py
    ├── test_service_report.py
    ├── test_repair.py
    └── test_applicant.py
```

## Class design

### `stock.lot` (`_inherit`)
| Field | Type |
|-------|------|
| `td_owner_id` | Many2one `res.partner`, `tracking=True`, `index=True`, string "Owner" |
| `td_applicant_ids` | One2many `td.equipment.applicant` / `lot_id` |
| `td_serviced_for_client` | Boolean, not stored, `search='_search_td_serviced_for_client'` (context `td_client_id`) |

Entry points: `write(vals)`, `@api.model _td_backfill_owners()`.

### `stock.picking` (`_inherit`)
Entry point: `_action_done()` (reached through standard `button_validate()`).

### `helpdesk.ticket` (`_inherit`)
| Field | Type |
|-------|------|
| `product_id` | override: `domain="[('tracking', '!=', 'none')]"`, string "Equipment" |
| `lot_id` | override: `domain="[('product_id', '=?', product_id)]"`, string "Serial Number" |
| `td_owner_id` | Many2one `res.partner`, readonly, string "Equipment Owner"; written by ticket `create` / `write(lot_id)` and by `stock.lot.write(td_owner_id)` for open tickets |
| `td_is_not_owner` | Boolean, compute, `store=True`, string "Not Owner" |
| `td_owner_notice` | Selection `none` / `warning` / `info`, compute, not stored |
| `td_applicant_edrpou` | Char, string "Applicant EDRPOU"; set from the client's `company_registry` by `create` / `write(partner_id)` / onchange |
| `td_applicant_id` | Many2one `td.equipment.applicant`, readonly, string "Applicant" |

Entry points:
- `@api.model _td_autofill_values(values) -> dict` — `{'record': {field: value}, 'custom': [str]}`
- `action_td_confirm_applicant()`, `action_td_make_owner()`
- `@api.model _td_migrate_equipment_fields()`, `@api.model _td_backfill_applicants()`
- standard: `_prepare_repairs_default_value()`, form onchanges (via `odoo.tests.Form`), `create`, `write`

### `td.equipment.applicant` (new)
`_name = 'td.equipment.applicant'`, `_description = 'Equipment Applicant'`,
`_inherit = ['mail.thread', 'mail.activity.mixin']`, `_order = 'lot_id, id'`.

| Field | Type |
|-------|------|
| `lot_id` | Many2one `stock.lot`, required, `ondelete='cascade'`, `index=True` |
| `product_id` | Many2one `product.product`, related `lot_id.product_id`, stored |
| `edrpou` | Char, `index=True` |
| `partner_id` | Many2one `res.partner` |
| `company_name`, `contact_name`, `phone` | Char |
| `ticket_ids` | One2many `helpdesk.ticket` / `td_applicant_id` |
| `ticket_count` | Integer, compute |
| `is_confirmed` | Boolean, `tracking=True` |
| `confirmed_uid` | Many2one `res.users` |
| `confirmed_date` | Datetime |

Constraints: `@api.constrains` for EDRPOU format without partner (AC-30) and pair uniqueness (AC-31),
both `ValidationError`.
Entry point: `@api.model _td_find_or_create(lot, partner, edrpou, vals)`.

### `td.service.report` (`_inherit`)
`partner_id` override: `related=False`, `readonly=False`, `compute='_compute_td_partner_id'`
(depends only on `ticket_id`), `store=True`, `precompute=True`, `tracking=True`.
Entry points: `default_get`, `create` (standard), `td_agreement_domain` compute.

### `td.agreement` (`_inherit`)
Entry points: `name_search(name, args, operator, limit)` and `display_name`, both reading the context
keys `td_agreement_client_id` and `td_agreement_lot_id`.

### `res.partner` (`_inherit`)
Entry points: `create`, `write` (AC-32).

### Controller
`controllers/website_form.py`:
`class WebsiteFormEquipment(WebsiteFormAutofill)` (from
`odoo.addons.td_medicus_helpdesk_website_autofill.controllers.website_form`).
- `@staticmethod _td_sanitize_values(values) -> dict` — drops `partner_id`, `product_id`, `lot_id`,
  `td_applicant_id`, `td_applicant_edrpou` (AC-20); `extract_data` calls it before `super()`.
- `_td_autofill_helpdesk(values, data)` override — replaces the parent's lookup: calls
  `request.env['helpdesk.ticket'].sudo()._td_autofill_values(values)`, merges `record` into
  `data['record']` and appends `custom` lines to `data['custom']`.

### Hook
`hooks.post_init_hook(env)` → `env['helpdesk.ticket']._td_migrate_equipment_fields()`,
`env['stock.lot']._td_backfill_owners()`, `env['helpdesk.ticket']._td_backfill_applicants()`.

## AC → test plan

Tag on every class: `@tagged('post_install', '-at_install', 'td_medicus_equipment_partner')`.

| AC | Test class.method (planned) | Entry point under test | Fixtures | Kind |
|----|-----------------------------|------------------------|----------|------|
| AC-01 | `TestLotOwner.test_ac01_sale_delivery_sets_owner` | `stock.picking.button_validate()` | `lot_l`, `contact_a`, `_deliver()` | auto |
| AC-02 | `TestLotOwner.test_ac02_storage_and_move_keep_owner` | `button_validate()` | `_deliver(..., 'act_res_st' / 'move')` | auto |
| AC-03 | `TestLotOwner.test_ac03_resale_changes_owner_and_tracks` | `button_validate()` | two `_deliver()` | auto |
| AC-04 | `TestLotOwner.test_ac04_return_clears_owner` | `button_validate()` of the return | `_deliver()`, `_return()` | auto |
| AC-05 | `TestLotOwner.test_ac05_backfill_replays_history` | `stock.lot._td_backfill_owners()` | deliveries, owner reset to empty | auto |
| AC-06 | `TestLotOwner.test_ac06_owner_write_needs_manager` | `stock.lot.write()` | `user_engineer`, `user_manager` | auto |
| AC-07 | `TestTicketEquipment.test_ac07_product_not_limited_to_sold` | field domain, `Form` | `product_device`, `company_b` | auto |
| AC-08 | `TestTicketEquipment.test_ac08_lot_domain_without_product` | evaluated `lot_id` domain + `search` | `lot_l`, `lot_other_product` | auto |
| AC-09 | `TestTicketEquipment.test_ac09_onchanges_keep_equipment` | `Form` onchanges | `lot_l`, `product_device2` | auto |
| AC-10 | `TestTicketEquipment.test_ac10_migrate_old_fields` | `_td_migrate_equipment_fields()` | ticket with `td_serial_number_id` (report row of a delivered lot) | auto |
| AC-11 | `TestTicketOwner.test_ac11_owner_and_flag` | `create` / `write` + computes | `lot_l` owned by `company_a` | auto |
| AC-12 | `TestTicketOwner.test_ac12_folded_ticket_frozen` | lot owner `write` | `stage_done` (`fold=True`) | auto |
| AC-13 | `TestTicketOwner.test_ac13_notice_warning` | `td_owner_notice` | as AC-11 | auto |
| AC-14 | `TestTicketOwner.test_ac14_search_filter` | `get_view(view_type='search')` | — | auto |
| AC-15 | — | ticket form banner, kanban badge | — | manual |
| AC-16 | `TestWebsiteForm.test_ac16_serial_and_edrpou_independent` | `_td_autofill_values()` | `lot_l`, `company_b` | auto |
| AC-17 | `TestWebsiteForm.test_ac17_unknown_edrpou` | `_td_autofill_values()` | `lot_l` | auto |
| AC-18 | `TestWebsiteForm.test_ac18_unknown_serial` | `_td_autofill_values()` | `company_b` | auto |
| AC-19 | `TestWebsiteForm.test_ac19_ambiguous_serial` | `_td_autofill_values()` | `lot_dup1`, `lot_dup2` (same name) | auto |
| AC-20 | `TestWebsiteForm.test_ac20_sanitize_protected_keys` | `WebsiteFormEquipment._td_sanitize_values()` | — | auto |
| AC-21 | `TestServiceReport.test_ac21_customer_editable_and_logged` | `td.service.report.create` / `write` | ticket of `contact_b` | auto |
| AC-22 | `TestServiceReport.test_ac22_customer_not_following_ticket` | ticket `write` | report of AC-21 | auto |
| AC-23 | `TestServiceReport.test_ac23_lot_from_ticket` | `default_get`, `create` | ticket with `lot_l` | auto |
| AC-24 | `TestServiceReport.test_ac24_ticket_agreement_domain` | `td_agreement_domain`, `Form` onchange | agreements X, Y, Z | auto |
| AC-25 | `TestServiceReport.test_ac25_agreement_order_and_label` | `td.agreement.name_search()` + context | agreements X, Y, Z | auto |
| AC-26 | `TestRepair.test_ac26_repair_defaults_from_ticket` | `_prepare_repairs_default_value()` | ticket B + `lot_l` (owner A) | auto |
| AC-27 | `TestRepair.test_ac27_quotation_for_ticket_client` | `repair.order.action_create_sale_order()` | repair from AC-26 values | auto |
| AC-28 | `TestApplicant.test_ac28_applicant_created_and_reused` | ticket `create` | `contact_b`, `lot_l` | auto |
| AC-29 | `TestApplicant.test_ac29_applicant_without_partner` | ticket `create` with `td_applicant_edrpou` | `lot_l` owned by `company_a` | auto |
| AC-30 | `TestApplicant.test_ac30_invalid_edrpou` | ticket `create`, applicant `create` | — | auto |
| AC-31 | `TestApplicant.test_ac31_unique_pair` | applicant `create` | — | auto |
| AC-32 | `TestApplicant.test_ac32_late_partner_link` | `res.partner.create` / `write` | applicant with `87654321` | auto |
| AC-33 | `TestApplicant.test_ac33_lot_change_repoints` | ticket `write` | `lot_l`, `lot_l2` | auto |
| AC-34 | `TestApplicant.test_ac34_confirm_applicant` | `action_td_confirm_applicant()` | not-owner ticket | auto |
| AC-35 | `TestApplicant.test_ac35_make_owner` | `action_td_make_owner()` | `user_manager`, `user_engineer` | auto |
| AC-36 | `TestApplicant.test_ac36_serviced_for_client_filter` | `stock.lot.search` + context | `lot_l`, `lot_l2`, `lot_l3` | auto |
| AC-37 | `TestApplicant.test_ac37_backfill_applicants` | `_td_backfill_applicants()` | tickets with applicant removed | auto |
| AC-38 | `TestApplicant.test_ac38_access_rights` | applicant `create` / `write` / `unlink` as users | `user_engineer`, `user_manager` | auto |
| AC-39 | — | lot form/list, ticket info line, buttons, menu | — | manual |

## Test fixtures (`tests/common.py`)

`TdEquipmentPartnerCase(TransactionCase)`, `setUpClass`:
- Users: `user_engineer` (`helpdesk.group_helpdesk_user`, `stock.group_stock_user`),
  `user_manager` (`helpdesk.group_helpdesk_manager`, `stock.group_stock_user`).
- Companies (`is_company=True`, `company_registry`): `company_a` `11111111`, `company_b`
  `12345678`, `company_e` `22222222`; contacts `contact_a` (delivery address of A), `contact_b`.
- Products: `product_device`, `product_device2` (`is_storable=True`, `tracking='serial'`).
- Lots: `lot_l`, `lot_l2`, `lot_l3` of `product_device`; `lot_other_product` of `product_device2`.
- Warehouse: `env.ref('stock.warehouse0')`, its `out_type_id`, `in_type_id`, stock location,
  `stock.stock_location_customers`.
- Helpdesk: a test team (`use_product_repairs=True`), an open stage and `stage_done` (`fold=True`).
- Helpers: `_put_in_stock(lot)`, `_deliver(lot, partner, implementation_document='exp_inv')`
  (outgoing picking + move line with the lot, `button_validate()`), `_return(picking)`
  (`stock.return.picking` wizard, validated), `_ticket(partner=None, lot=None, **vals)`.
- Lots and partners use names that do not exist on the client DB (prefix `TD-EP-`), because the
  tests run on `medicus`.

## Mock points
None. The module has no external calls; the website form is tested through
`helpdesk.ticket._td_autofill_values()` and the static `_td_sanitize_values()`, without HTTP.

## Dependencies
```python
'depends': [
    'helpdesk_stock',        # ticket product_id / lot_id
    'helpdesk_repair',       # Repair button defaults (AC-26, AC-27)
    'td_medicus_agreement',  # stock.picking.implementation_document (AC-01, AC-02)
    'td_medicus_helpdesk_website_autofill',  # controller being extended (AC-16…AC-20)
    'td_medicus_service_report',  # td.service.report, td.agreement.td_lot_ids (AC-21…AC-25)
],
```

## Migration plan
New module, no `migrations/`. Data of existing records is handled by `post_init_hook`:
ticket equipment fields (AC-10), lot owners from history (AC-05), applicants (AC-37).

## Odoo.sh considerations
- Feature branch: `18.0-td_medicus_equipment_partner-yhorodnii` (repo convention), merged into
  `18.0-medicus-test1` for the test environment.
- Add `todoltd/service` modules to the deployment as usual; no config params, no external config.

## Open technical decisions
None blocking. Decided:
- `helpdesk.ticket.td_owner_id` is a plain stored field written explicitly: on ticket `create`,
  on `write` of `lot_id`, and from `stock.lot.write(td_owner_id)` for tickets whose stage is not
  folded (AC-12). A stored compute cannot reliably read its own previous value to stay frozen.
- `td.service.report.partner_id` drops `related` with `related=False` and becomes a stored
  compute on `ticket_id` only, so later changes of the ticket client do not overwrite it (AC-22).
