# Architecture: td_medicus_report
Generated from SPEC.md v18.0.1.0.55 — 2026-04-15

---

## File structure (current)

```
td_medicus_report/
├── __init__.py
├── __manifest__.py                         # v18.0.1.0.55, depends: account, mrp, sale, stock, hr, fleet, ...
├── models/
│   ├── __init__.py
│   ├── td_amound_to_words_mixin.py         # AbstractModel — конвертація числа у слова (UA)
│   ├── res_company.py                      # +7 полів відповідальних осіб (hr.employee)
│   ├── res_partner.py                      # +td_partner_short_name, contact_address_complete, use_in_vendor_refund_report
│   ├── hr_employee.py                      # +td_partner_short_name, td_driver_license_number
│   ├── fleet_vehicle.py                    # +td_transport_ownership, td_body_length/width/height
│   ├── stock_location.py                   # +td_condition_ids (M2M → td.stock.condition)
│   ├── td_stock_condition.py               # NEW model — словник умов зберігання
│   ├── sale_order.py                       # +td_invoice_from_delivery, td_get_co_data()
│   ├── account_move.py                     # +mixin, td_get_invoice_report_data(), td_get_report_data()
│   ├── ir_actions_report.py                # override _render_qweb_pdf → UserError wrapper
│   └── stock_picking.py                    # +TTН-поля, кнопки, всі report_data методи
├── views/
│   ├── res_company_views.xml               # group "Responsible Persons"
│   ├── res_partner_views.xml               # td_partner_short_name, use_in_vendor_refund_report
│   ├── hr_employee_views.xml               # td_partner_short_name, td_driver_license_number
│   ├── fleet_vehicle_views.xml             # group "Body Parameters"
│   ├── stock_location_views.xml            # page "Conditions" з td_condition_ids
│   ├── td_stock_condition_views.xml        # list + action + menuitem
│   └── stock_picking_views.xml             # header buttons, дати, page "Дані для ТТН"
├── report/
│   ├── report_actions.xml                  # 16 ir.actions.report + 2 paper formats
│   └── report_template.xml                 # QWeb шаблони всіх звітів
├── security/
│   └── ir.model.access.csv                 # доступ до td.stock.condition, td.amount.to.words.mixin
├── static/
│   ├── img/
│   │   ├── medicus_logo.png
│   │   └── medicus_partners.png
│   └── src/css/
│       └── wholesale_invoice.css           # стилі для звітів
└── i18n/
    └── uk_UA.po
```

---

## Class design

### `TdAmountToWordsMixin` (`td.amount.to.words.mixin`)
```python
class TdAmountToWordsMixin(models.AbstractModel):
    _name = 'td.amount.to.words.mixin'
    _description = 'Mixin to convert amount to words in Ukrainian'

    def _amount_to_words_ua(self, amount: float, count=False, weight=False) -> str:
        # AC: використовується у всіх report_data методах
        # Режими:
        #   default  → "Сто двадцять три гривні 45 копійок"
        #   count    → "сто двадцять три"  (кількість місць)
        #   weight   → "сто двадцять три т 45 кг"
```

---

### `ResCompany` (`res.company`)
```python
class ResCompany(models.Model):
    _inherit = 'res.company'

    # ── Fields ────────────────────────────────────────────────────
    td_warehouse_manager_id          # Many2one hr.employee
    td_medical_warehouse_manager_id  # Many2one hr.employee
    td_responsible_manager_id        # Many2one hr.employee
    td_president_id                  # Many2one hr.employee
    td_head_medical_equipment_sales_id  # Many2one hr.employee
    td_medical_equipment_engineer_id    # Many2one hr.employee
    td_vice_president_id             # Many2one hr.employee
```

---

### `ResPartner` (`res.partner`)
```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Fields ────────────────────────────────────────────────────
    td_partner_short_name           # Char — коротке ім'я для підписів
    contact_address_complete        # Char compute, store=False — AC-VR-01
    use_in_vendor_refund_report     # Boolean — AC-VR-01

    # ── Compute ───────────────────────────────────────────────────
    def _td_compute_complete_address(self)
        # zip + country + state + city + street + street2

    # ── Override ──────────────────────────────────────────────────
    def write(self, vals)           # ексклюзивність use_in_vendor_refund_report
    def create(self, vals_list)     # ексклюзивність use_in_vendor_refund_report

    # ── Onchange ──────────────────────────────────────────────────
    def _onchange_use_in_vendor_refund_report(self)
```

---

### `HrEmployee` (`hr.employee`)
```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    td_partner_short_name      # Char
    td_driver_license_number   # Char — джерело для td_ttn_driver_license_number при виборі водія
```

---

### `FleetVehicle` (`fleet.vehicle`)
```python
class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    td_transport_ownership   # Selection own/hired — domain для td_ttn_vehicle_id
    td_body_length           # Float(16,3) — джерело для compute габаритів ТТН
    td_body_width            # Float(16,3)
    td_body_height           # Float(16,3)

    # ── Override compute ──────────────────────────────────────────
    def _compute_vehicle_name(self)   # Бренд/Модель (без номерного знаку)
```

---

### `StockLocation` (`stock.location`)
```python
class StockLocation(models.Model):
    _inherit = 'stock.location'

    td_condition_ids   # Many2many td.stock.condition — умови зберігання у звітах
```

---

### `TDStockCondition` (`td.stock.condition`)
```python
class TDStockCondition(models.Model):
    _name = 'td.stock.condition'
    _description = 'Stock Condition'

    name         # Char, required=True
    description  # Text
```

---

### `SaleOrder` (`sale.order`)
```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    td_invoice_from_delivery   # Boolean, default=False

    def copy(self, default=None)     # скидає td_invoice_from_delivery=False
    def td_get_co_data(self) -> dict # AC: Комерційна пропозиція
        # Повертає: company_info, co_date, co_number, consignee, groups[{section, lines}], total
```

---

### `AccountMove` (`account.move`)
```python
class AccountMove(models.Model):
    _inherit = ['account.move', 'td.amount.to.words.mixin']

    def get_amount_in_words(self) -> str
    def td_get_invoice_report_data(self) -> dict   # простий (один рядок = один invoice_line)
    def td_get_report_data(self) -> dict           # розширений (розбивка по лотах)
        # Обидва повертають однакову структуру:
        # { is_invoice, company{}, company_partner{}, partner{}, payment_partner,
        #   agreement{}, document_number, document_date, payment_term,
        #   lines[{sequence, product_name, serial_numbers, expiration_dates, ...}],
        #   amount_untaxed, amount_tax, amount_total, amount_in_words }
```

---

### `StockPicking` (`stock.picking`) — центральний клас модуля
```python
class StockPicking(models.Model):
    _inherit = ['stock.picking', 'td.amount.to.words.mixin']

    # ── Загальні поля ─────────────────────────────────────────────
    td_invoice_date                      # Date
    td_custody_act_date                  # Date
    td_order_implementation_document     # Selection related store=True
    td_show_create_invoice_button        # Boolean compute — AC-INV-01
    td_show_create_custody_act_button    # Boolean compute — AC-CUST-01
    td_invoice_for_pick_id               # Many2one account.move

    # ── ТТН: транспорт (own) ──────────────────────────────────────
    td_ttn_transport_type                # Selection own/hired, default own
    td_ttn_vehicle_id                    # Many2one fleet.vehicle — AC-WB-01, AC-WB-02
    td_ttn_license_number                # Char related fleet.vehicle.license_plate
    td_ttn_driver_employee_id            # Many2one hr.employee — AC-WB-01
    td_ttn_carrier_partner_id            # Many2one res.partner — AC-WB-01
    td_ttn_driver_license_number         # Char — спільне для own/hired — AC-WB-01
    td_ttn_driver_forwarder              # Char

    # ── ТТН: транспорт (hired) ────────────────────────────────────
    td_ttn_hired_vehicle                 # Char — AC-WB-01
    td_ttn_license_number_other          # Char
    td_ttn_hired_driver                  # Char — AC-WB-01
    td_ttn_hired_carrier                 # Char — AC-WB-01

    # ── ТТН: legacy (прихований) ──────────────────────────────────
    td_ttn_driver_partner_id             # Many2one res.partner, invisible="1"

    # ── ТТН: вантаж та габарити ───────────────────────────────────
    td_ttn_places_count                  # Char
    td_ttn_gross_weight_                 # Float (tech debt: trailing _)
    td_ttn_vehicle_dimensions_manual     # Boolean default=False — AC-WB-02
    td_ttn_vehicle_length                # Float compute+inverse, store=True — AC-WB-02
    td_ttn_vehicle_width                 # Float compute+inverse, store=True
    td_ttn_vehicle_height                # Float compute+inverse, store=True

    # ── Compute ───────────────────────────────────────────────────
    def _compute_td_show_create_invoice_button(self)    # AC-INV-01
    def _compute_td_show_create_custody_act_button(self) # AC-CUST-01
    def _compute_td_ttn_vehicle_dimensions(self)        # AC-WB-02
    def _inverse_td_ttn_vehicle_dimensions(self)        # AC-WB-02 → manual=True

    # ── Onchange ──────────────────────────────────────────────────
    def _onchange_td_ttn_transport_type(self)           # AC-WB-01: скидання при зміні типу
    def _onchange_td_ttn_vehicle_id(self)               # AC-WB-02: підставлення габаритів
    def _onchange_td_ttn_driver_employee_id(self)       # AC-WB-01: license_number, forwarder
    def _onchange_td_ttn_driver_partner_id(self)        # legacy, carrier_partner_id
    def _onchange_td_dates(self)                        # синхронізація дат

    # ── Дії (кнопки) ──────────────────────────────────────────────
    def td_create_invoice(self)      # AC-INV-01
    def td_create_custody_act(self)  # AC-CUST-01

    # ── Допоміжні ─────────────────────────────────────────────────
    def _sync_invoice_date_in_chain(self, invoice_date, custody_date)
    def get_amount_in_words(self) -> str
    def _get_waybill_transport_info(self, transport_type) -> dict  # AC-WB-01

    # ── Report data методи ────────────────────────────────────────
    def td_get_report_data(self) -> dict              # → делегує до account.move
    def td_get_report_lenses_data(self) -> dict       # Для складу
    def td_get_report_waybill_data(self) -> dict      # ТТН — AC-WB-01
    def td_get_report_custody_act_data(self) -> dict  # Акти зберігання — AC-CUST-01
    def td_get_custody_balance_data(self) -> dict     # Акт звірки — AC-BAL-01
    def td_get_report_refund_data(self) -> dict       # Накладна на повернення
    def td_get_vendor_refund_act_data(self) -> dict   # Повернення постачальнику — AC-VR-01
```

---

## AC Traceability

| AC | Де реалізовано | Тип |
|----|----------------|-----|
| AC-WB-01 | `StockPicking._get_waybill_transport_info()` | method |
| AC-WB-01 | `views/stock_picking_views.xml` — `invisible` на полях транспорту | view |
| AC-WB-02 | `StockPicking._compute_td_ttn_vehicle_dimensions()` | compute |
| AC-WB-02 | `StockPicking._inverse_td_ttn_vehicle_dimensions()` | inverse |
| AC-WB-02 | `StockPicking._onchange_td_ttn_vehicle_id()` | onchange |
| AC-WB-02 | `views/stock_picking_views.xml` — `readonly="td_ttn_transport_type == 'own'"` на габаритах | view |
| AC-INV-01 | `StockPicking._compute_td_show_create_invoice_button()` | compute |
| AC-INV-01 | `StockPicking.td_create_invoice()` | method |
| AC-INV-01 | `views/stock_picking_views.xml` — кнопка з `invisible` | view |
| AC-CUST-01 | `StockPicking._compute_td_show_create_custody_act_button()` | compute |
| AC-CUST-01 | `StockPicking.td_create_custody_act()` | method |
| AC-BAL-01 | `StockPicking.td_get_custody_balance_data()` | method |
| AC-VR-01 | `ResPartner.write()` / `create()` / `_onchange_use_in_vendor_refund_report()` | method |
| AC-VR-01 | `StockPicking.td_get_vendor_refund_act_data()` | method |
| AC-VR-01 | `views/res_partner_views.xml` — `invisible="type != 'contact' or not parent_id"` | view |

---

## Data flows

### 1. Друк ТТН (AC-WB-01)
```
Користувач відкриває outgoing-переміщення
  → вкладка "Дані для ТТН" (invisible якщо picking_type_code != 'outgoing')
    → вибирає td_ttn_transport_type
      → 'own':
          _onchange_td_ttn_transport_type()
            → td_carrier_partner_id = company.partner_id
            → скидає hired-поля
          → вибирає td_ttn_vehicle_id
              _onchange_td_ttn_vehicle_id()
                → td_ttn_vehicle_length/width/height ← fleet.vehicle.td_body_*
                → td_ttn_vehicle_dimensions_manual = False
          → вибирає td_ttn_driver_employee_id
              _onchange_td_ttn_driver_employee_id()
                → td_ttn_driver_license_number ← hr.employee.td_driver_license_number
                → td_ttn_driver_forwarder ← partner.full_partner_name
      → 'hired':
          _onchange_td_ttn_transport_type()
            → скидає own-поля, габарити → 0.0
          → заповнює текстові поля вручну
  → Зберігає переміщення
  → Друк "Товарно-транспортна"
      → IrActionsReport._render_qweb_pdf()
          → StockPicking.td_get_report_waybill_data()
              → _get_waybill_transport_info(transport_type)
                  if own:  vehicle=vehicle_id.name, driver=employee.name, carrier=partner.name
                  if hired: vehicle=hired_vehicle, driver=hired_driver, carrier=hired_carrier
              → dict з waybill_info, lines[], ...
          → QWeb template рендерить PDF
```

### 2. Створення інвойсу з переміщення (AC-INV-01)
```
Стан: picking done, impl_doc=exp_inv, всі пов'язані pickings done,
       td_invoice_from_delivery=False
  → td_show_create_invoice_button = True → кнопка "Create Invoice" видима
  → Клік → td_create_invoice()
      → sale.advance.payment.inv.create(delivered).create_invoices()
      → invoice.invoice_date = td_invoice_date or today
      → invoice.action_post()
      → sale_order.td_invoice_from_delivery = True
      → sale_order.picking_ids.write(td_invoice_for_pick_id=invoice.id)
      → return action_report_wholesale_invoice_invoice.report_action(invoice)
          → AccountMove.td_get_invoice_report_data() або td_get_report_data()
          → PDF
```

### 3. Акт звірки залишків (AC-BAL-01)
```
Вхід: incoming picking, act_res_st, done
  → Друк "Акт звірки залишків"
      → StockPicking.td_get_custody_balance_data()
          1. search всі outgoing act_res_st done по td_parent_partner_id
             → для кожного move_line: product_balances[sale_id, product_id, lot_id]['transferred'] += qty
          2. search всі incoming act_res_st done по td_parent_partner_id
             → для відповідних ключів: ['returned'] += qty
          3. remaining = transferred - returned
             → лише > 0 потрапляють у lines[]
          4. групування по sale_order → documents[]
          5. сума agreement_number/date (якщо одна угода)
          → dict { company{}, partner{}, documents[], amount_total, amount_in_words }
```

### 4. Ексклюзивність use_in_vendor_refund_report (AC-VR-01)
```
Користувач відмічає use_in_vendor_refund_report = True на контакті
  → _onchange_use_in_vendor_refund_report() (UI)
      → search інших контактів з тим же parent_id
      → write({use_in_vendor_refund_report: False})
  → write() (збереження)
      → аналогічна логіка для впевненості (DB-рівень)
  → Друк "Повернення постачальнику"
      → td_get_vendor_refund_act_data()
          → vendor_partner.child_ids.filtered(use_in_vendor_refund_report=True)[0]
          → vendor_recipient_name → у поле 'vendor_recipient' звіту
```

---

## Dependencies

```python
'depends': [
    'account',                       # account.move, journal entries
    'mrp',                           # компоненти у комерційній пропозиції
    'sale',                          # sale.order, sale.advance.payment.inv
    'stock',                         # stock.picking, stock.location, stock.move
    'hr',                            # hr.employee (водій, підписанти)
    'fleet',                         # fleet.vehicle (ТТН — власний транспорт)
    'account_disallowed_expenses_fleet',  # fleet залежність
    'td_contact_sale',               # full_partner_name, implementation_document, warehouse_address_id
    'td_medicus_agreement',          # td_agreement_id, agreement_number
    'td_medicus_1c_integration',     # td_untaxed_price_unit, td_price_unit, td_total_amount, td_tax_guide_id
]
```

> Поля `td_untaxed_price_unit`, `td_price_unit`, `td_price_subtotal`, `td_price_total`, `td_total_amount`, `td_total_tax`, `td_total_without_tax`, `td_amount_origin_currency`, `td_taxes_price`, `td_parent_partner_id`, `td_supplier_document`, `td_date_supplier_document`, `implementation_document`, `warehouse_address_id` надходять з модулів-залежностей, а не визначаються у цьому модулі.

---

## Migration plan

### Поточна версія: 18.0.1.0.55

Зміни у поточній версії (відносно попередніх знімків):
- Логіку `waybill_info` винесено у `_get_waybill_transport_info()` — **зворотньо сумісна** (тільки рефакторинг).

### Майбутній tech debt (потребує міграції при виправленні)

| Поле | Проблема | SQL при виправленні |
|------|----------|---------------------|
| `td_ttn_gross_weight_` | trailing `_` у імені | `ALTER TABLE stock_picking RENAME COLUMN td_ttn_gross_weight_ TO td_ttn_gross_weight;` |

> Міграційний скрипт: `migrations/18.0.1.0.56/pre-migration.py`

---

## Odoo.sh considerations

### Branch strategy
- Feature branches → merge to `staging` → production `main`
- Цей модуль не має зовнішніх API-викликів — deployment ризик мінімальний

### Build hooks
Не потрібні.

### Required config params
Відсутні (`ir.config_parameter` не використовується).

### Assets
- `td_medicus_report/static/src/css/wholesale_invoice.css` підключається через `web.report_assets_common` — застосовується до всіх PDF-звітів системи.

---

## Відкриті технічні рішення

> Ці питання мають бути вирішені до наступної ітерації розробки.

| # | Питання | Рекомендація |
|---|---------|--------------|
| TD-1 | `td_ttn_driver_partner_id` — видалити поле і onchange? | Підтвердити що немає зовнішніх залежностей → видалити, очистити onchange |
| TD-2 | `td_transport_ownership` на `fleet.vehicle` — показувати у view? | Розкоментувати XPath або видалити поле якщо не потрібне |
| TD-3 | Виправити `td_ttn_gross_weight_` → `td_ttn_gross_weight` | Потрібна міграція БД + оновлення всіх посилань у views та report_data |
| TD-4 | `REPORT_IDS` у `ir_actions_report.py` — реалізувати або видалити | Видалити якщо функціональність скасована |
| TD-5 | `sertificate_number` у `td_get_co_data` — перенести у `res.company` | Додати поле `td_certificate_number: Char` на компанію |
| TD-6 | Окреме поле ліцензії для `hired` | Додати `td_ttn_hired_driver_license_number: Char` і розвести логіку |
