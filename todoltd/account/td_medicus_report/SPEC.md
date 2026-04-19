# Module: td_medicus_report

## Status
approved

## Version history
| Версія | Дата | Автор | Опис змін |
|--------|------|-------|-----------|
| 18.0.1.0.55 | 2026-04-15 | reverse-spec AI | Початковий reverse-spec зі source-коду |
| 18.0.1.0.55 | 2026-04-15 | developer | Умовне формування `waybill_info` залежно від типу перевезення (`own` / `hired`) |
| 18.0.1.0.55 | 2026-04-15 | architecture AI | Уточнення після перевірки всіх views; відкриті питання закриті; статус → approved |

## Версія Odoo
18.0

## Бізнес-призначення
Модуль генерує українські звітні документи (PDF / QWeb) для медичної торгової компанії Medicus:
оптові накладні, товарно-транспортні накладні (ТТН), акти передачі / повернення на відповідальне
зберігання, акт звірки залишків, рахунки-фактури, накладні на повернення, акти комплектації та
комерційні пропозиції. Модуль розширює стандартні моделі Odoo (`stock.picking`, `account.move`,
`sale.order`, `res.partner`, `hr.employee`, `fleet.vehicle`, `stock.location`) додатковими полями,
необхідними для формування юридично-значущих документів за вимогами українського законодавства.

---

## User Stories

| # | Роль | Дія | Результат |
|---|------|-----|-----------|
| US-01 | Менеджер зі складу | Натискаю "Create Invoice" у переміщенні з типом `exp_inv` | Автоматично створюється та підтверджується інвойс; одразу друкується оптова накладна |
| US-02 | Менеджер зі складу | Натискаю "Transfer Act" / "Return Act" у переміщенні з типом `act_res_st` | Друкується акт передачі або повернення майна на відповідальне зберігання |
| US-03 | Логіст | Заповнюю вкладку "Дані для ТТН" у outgoing-переміщенні | Дані транспорту / водія / перевізника потрапляють до друкованої ТТН |
| US-04 | Логіст (власний авто) | Вибираю `td_ttn_transport_type = own`, вказую `fleet.vehicle` та `hr.employee`-водія | ТТН формується з даними власного транспорту та водія-співробітника |
| US-05 | Логіст (сторонній перевізник) | Вибираю `td_ttn_transport_type = hired`, заповнюю текстові поля | ТТН формується з даними найманого транспорту та стороннього перевізника |
| US-06 | Менеджер | Відкриваю будь-яке `account.move` з типом `out_invoice` | Доступний друк "Рахунок-фактура" та "Комерційна пропозиція" |
| US-07 | Системний адміністратор | Налаштовую `res.company` → відповідальні особи (завскладом, президент тощо) | Ці особи автоматично підписують всі звіти компанії |
| US-08 | Менеджер | Друкую "Повернення постачальнику" | Контакт з `use_in_vendor_refund_report=True` виступає отримувачем у документі |
| US-09 | Адміністратор складу | Налаштовую умови зберігання через Inventory > Configuration > Stock Conditions | Умови зберігання прив'язуються до локацій і виводяться у звітах |

---

## Моделі

### TdAmountToWordsMixin (`td.amount.to.words.mixin`)
Абстрактний міксін для конвертації числа у слова українською мовою.

| Метод | Параметри | Опис |
|-------|-----------|------|
| `_amount_to_words_ua(amount, count, weight)` | float, bool, bool | Конвертує число у рядок. Режими: гривні+копійки (default), кількість місць (`count=True`), вага т+кг (`weight=True`) |

**Успадковується:** `account.move`, `stock.picking`

---

### ResCompany (`res.company`) — розширення
Inherits: `res.company`

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `td_warehouse_manager_id` | Many2one → `hr.employee` | ні | Завідувач складом |
| `td_medical_warehouse_manager_id` | Many2one → `hr.employee` | ні | Завідувач медичним складом |
| `td_responsible_manager_id` | Many2one → `hr.employee` | ні | Відповідальний менеджер |
| `td_president_id` | Many2one → `hr.employee` | ні | Президент |
| `td_head_medical_equipment_sales_id` | Many2one → `hr.employee` | ні | Керівник відділу продажу медобладнання |
| `td_medical_equipment_engineer_id` | Many2one → `hr.employee` | ні | Інженер медичного обладнання |
| `td_vice_president_id` | Many2one → `hr.employee` | ні | Віце-президент |

> View: поля розміщені у новій групі "Responsible Persons" всередині стандартної форми компанії.

---

### ResPartner (`res.partner`) — розширення
Inherits: `res.partner`

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `td_partner_short_name` | Char | ні | Скорочене ім'я (використовується у підписах звітів замість повного) |
| `contact_address_complete` | Char (compute, store=False) | — | Повна адреса: індекс, країна, область, місто, вулиця, вулиця2 |
| `use_in_vendor_refund_report` | Boolean | ні | Позначає основний контакт-отримувач для звіту "Повернення постачальнику"; видиме лише для `type=contact` з `parent_id` |

**Ключові методи:**
- `_td_compute_complete_address()` — обчислює `contact_address_complete` (не зберігається у БД)
- `write()` / `create()` — при `use_in_vendor_refund_report=True` скидають прапор усіх інших контактів того ж `parent_id`
- `_onchange_use_in_vendor_refund_report()` — аналогічна логіка в UI

> Поле `td_driver_license_number` на `res.partner` закоментовано (є лише на `hr.employee`).

---

### HrEmployee (`hr.employee`) — розширення
Inherits: `hr.employee`

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `td_partner_short_name` | Char | ні | Скорочене ім'я (для підписів у звітах) |
| `td_driver_license_number` | Char | ні | Номер водійського посвідчення |

> View: `td_partner_short_name` — перед `work_email`; `td_driver_license_number` — перед `private_car_plate`.

---

### FleetVehicle (`fleet.vehicle`) — розширення
Inherits: `fleet.vehicle`

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `td_transport_ownership` | Selection (`own`/`hired`) | ні | Тип власності ТЗ; default `own`. **Не відображається у view** (xpath закоментований) |
| `td_body_length` | Float (16,3) | ні | Довжина кузова, м |
| `td_body_width` | Float (16,3) | ні | Ширина кузова, м |
| `td_body_height` | Float (16,3) | ні | Висота кузова, м |

**Ключові методи:**
- `_compute_vehicle_name()` — перевизначає ім'я ТЗ: `Бренд/Модель` (без номерного знаку)

> View: група "Body Parameters" з габаритами додається до стандартної форми.

---

### StockLocation (`stock.location`) — розширення
Inherits: `stock.location`

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `td_condition_ids` | Many2many → `td.stock.condition` | ні | Умови зберігання локації; виводяться у всіх товарних звітах |

> View: нова вкладка "Conditions" у формі локації.

---

### TDStockCondition (`td.stock.condition`)
Нова самостійна модель. Словник умов зберігання.

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `name` | Char | **так** | Назва умови зберігання |
| `description` | Text | ні | Опис |

> Menu: Inventory → Configuration → Stock Conditions (sequence 10, list view, editable bottom)

---

### SaleOrder (`sale.order`) — розширення
Inherits: `sale.order`

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `td_invoice_from_delivery` | Boolean | ні | Ознака того, що інвойс вже створено з переміщення; default `False`; скидається при `copy()` |

**Ключові методи:**
- `td_get_co_data()` — формує dict для звіту "Комерційна пропозиція" із замовлення на продаж

---

### AccountMove (`account.move`) — розширення
Inherits: `account.move`, `td.amount.to.words.mixin`

**Ключові методи:**
- `get_amount_in_words()` — `amount_total` словами (українська)
- `td_get_invoice_report_data()` — dict для "Оптова накладна" (простий варіант, один рядок на інвойс-рядок)
- `td_get_report_data()` — dict для "Оптова накладна" (розширений: групування по лотах, ціни без ПДВ)

---

### StockPicking (`stock.picking`) — розширення
Inherits: `stock.picking`, `td.amount.to.words.mixin`

#### Загальні поля

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `td_invoice_date` | Date | ні | Дата інвойсу; видиме при `impl_doc=exp_inv` |
| `td_custody_act_date` | Date | ні | Дата акту зберігання; видиме при `impl_doc=act_res_st` |
| `td_order_implementation_document` | Selection (related, store=True) | ні | Тип документа реалізації з `sale.order` |
| `td_show_create_invoice_button` | Boolean (compute) | — | Умова показу кнопки "Create Invoice" |
| `td_show_create_custody_act_button` | Boolean (compute) | — | Умова показу кнопок "Transfer Act" / "Return Act" |
| `td_invoice_for_pick_id` | Many2one → `account.move` | ні | Пов'язаний інвойс |

#### Поля ТТН — транспорт

| Поле | Тип | Видимість у view | Опис |
|------|-----|-----------------|------|
| `td_ttn_transport_type` | Selection (`own`/`hired`) | завжди | Тип перевезення; default `own` |
| `td_ttn_vehicle_id` | Many2one → `fleet.vehicle` | `own` | Власний автомобіль |
| `td_ttn_license_number` | Char (related) | `own` | Номерний знак власного ТЗ |
| `td_ttn_driver_employee_id` | Many2one → `hr.employee` | `own` | Водій-співробітник |
| `td_ttn_carrier_partner_id` | Many2one → `res.partner` | `own` | Автомобільний перевізник |
| `td_ttn_driver_license_number` | Char | `own` + `hired` | Номер водійського посвідчення (спільне поле) |
| `td_ttn_driver_forwarder` | Char | `own` + `hired` | Отримав водій/експедитор |
| `td_ttn_hired_vehicle` | Char | `hired` | Найманий автомобіль (текст) |
| `td_ttn_license_number_other` | Char | `hired` | Номерний знак найманого ТЗ |
| `td_ttn_hired_driver` | Char | `hired` | Водій найманого перевізника |
| `td_ttn_hired_carrier` | Char | `hired` | Автомобільний перевізник (текст) |
| `td_ttn_driver_partner_id` | Many2one → `res.partner` | **прихований** | Водій-контакт (legacy, `invisible="1"`) |

#### Поля ТТН — вантаж та габарити

| Поле | Тип | Обов'язкове | Опис |
|------|-----|-------------|------|
| `td_ttn_places_count` | Char | ні | Кількість місць |
| `td_ttn_gross_weight_` | Float | ні | Маса брутто, т *(ім'я із зайнім `_` — tech debt)* |
| `td_ttn_vehicle_dimensions_manual` | Boolean | ні | Ознака ручного введення габаритів; default `False` |
| `td_ttn_vehicle_length` | Float (16,3) compute+inverse | ні | Довжина кузова, м; readonly при `own` (береться з ТЗ) |
| `td_ttn_vehicle_width` | Float (16,3) compute+inverse | ні | Ширина кузова, м |
| `td_ttn_vehicle_height` | Float (16,3) compute+inverse | ні | Висота кузова, м |

**Ключові обчислення:**
- `_compute_td_ttn_vehicle_dimensions` — залежить від `td_ttn_vehicle_id.*`, `td_ttn_vehicle_dimensions_manual`. При виборі ТЗ підставляє габарити; якщо `manual=True` — не перезаписує.
- `_inverse_td_ttn_vehicle_dimensions` — при ручному редагуванні встановлює `manual=True`.

**Ключові onchange:**
- `_onchange_td_ttn_transport_type` — скидає `driver_license_number`, `driver_forwarder`; для `own`: `carrier_partner_id` = партнер компанії; для `hired`: скидає `vehicle_id`, `driver_employee_id`, габарити.
- `_onchange_td_ttn_driver_employee_id` — при `own` підставляє `driver_license_number` з `hr.employee`, `driver_forwarder` з повного імені.
- `_onchange_td_ttn_driver_partner_id` — при `hired` підставляє `carrier_partner_id` (legacy, не використовується через прихований UI).

**Ключові методи:**
- `td_create_invoice()` — створює інвойс через `sale.advance.payment.inv`, підтверджує, синхронізує `td_invoice_for_pick_id` по всіх переміщеннях замовлення, друкує оптову накладну.
- `td_create_custody_act()` — встановлює `td_custody_act_date` при потребі, друкує відповідний акт.
- `_sync_invoice_date_in_chain()` — синхронізує дати по всіх не-скасованих переміщеннях замовлення.
- `_get_waybill_transport_info(transport_type)` — умовно формує блок `waybill_info` (see AC-WB-01).
- `td_get_report_waybill_data()` — повний dict для ТТН-звіту.
- `td_get_report_lenses_data()` — dict для "Для складу" з розбивкою по лотах.
- `td_get_report_custody_act_data()` — dict для актів відповідального зберігання.
- `td_get_custody_balance_data()` — dict для акту звірки залишків: шукає всі `outgoing` + `incoming` переміщення типу `act_res_st` по `td_parent_partner_id`, обчислює залишок `transferred − returned` по ключу `(sale_id, product_id, lot_id)`.
- `td_get_report_refund_data()` — dict для "Накладна на повернення".
- `td_get_vendor_refund_act_data()` — dict для "Повернення постачальнику" (використовує `use_in_vendor_refund_report`).

---

## Acceptance Criteria

### AC-WB-01 Умовне формування waybill_info
**Given** переміщення відкрите для друку ТТН  
**When** `td_ttn_transport_type == 'own'`  
**Then** у `waybill_info`:
- `vehicle` ← `td_ttn_vehicle_id.name` (/ → пробіл)
- `driver` ← `td_ttn_driver_employee_id.name`
- `driver_license` ← `td_ttn_driver_license_number`
- `carrier_partner` ← `td_ttn_carrier_partner_id.full_partner_name`

**When** `td_ttn_transport_type == 'hired'`  
**Then** у `waybill_info`:
- `vehicle` ← `td_ttn_hired_vehicle`
- `driver` ← `td_ttn_hired_driver`
- `driver_license` ← `td_ttn_driver_license_number`
- `carrier_partner` ← `td_ttn_hired_carrier`

**Спільно для обох типів:** `transport_type`, `places_count`, `gross_weight`, `driver_forwarder`, `vehicle_length`, `vehicle_width`, `vehicle_height`

### AC-WB-02 Габарити кузова
**When** обрано власний ТЗ і `td_ttn_vehicle_dimensions_manual == False`  
**Then** `vehicle_length/width/height` беруться з `fleet.vehicle.td_body_*` автоматично  
**When** користувач редагує будь-який габарит вручну  
**Then** `td_ttn_vehicle_dimensions_manual` → `True`; авто-оновлення зупиняється

### AC-INV-01 Створення інвойсу з переміщення
**Given** переміщення `exp_inv`, стан `done`, всі пов'язані переміщення виконані, `td_invoice_from_delivery=False`  
**When** натискаю "Create Invoice"  
**Then** → інвойс створений та підтверджений → `td_invoice_for_pick_id` встановлено на всіх переміщеннях замовлення → `td_invoice_from_delivery=True` → друк оптової накладної

### AC-CUST-01 Друк актів відповідального зберігання
**Given** переміщення `act_res_st`, стан `done`  
**When** натискаю "Transfer Act" (outgoing) або "Return Act" (incoming)  
**Then** `td_custody_act_date` встановлюється (якщо порожнє) → друкується відповідний акт

### AC-BAL-01 Акт звірки залишків
**Given** переміщення `incoming`, `act_res_st`, `done`  
**When** друкую "Акт звірки залишків"  
**Then** система знаходить всі `outgoing act_res_st` переміщення по `td_parent_partner_id`, підраховує `transferred − returned` по `(sale_id, product_id, lot_id)`, виводить лише рядки з `remaining_qty > 0`

### AC-VR-01 Контакт для повернення постачальнику
**Given** партнер має кілька контактів типу `contact`  
**When** один контакт отримує `use_in_vendor_refund_report=True`  
**Then** у решти контактів того ж `parent_id` прапор знімається; у звіті "Повернення постачальнику" виводиться ПІБ цього контакту як отримувача

---

## Views & menus

| XML id | Модель | Тип view | Опис |
|--------|--------|----------|------|
| `td_view_picking_form_inherit` | `stock.picking` | form inherit | Кнопки у header; дати; вкладка "Дані для ТТН" (тільки outgoing) |
| `td_view_company_form_responsible` | `res.company` | form inherit | Група "Responsible Persons" |
| `res_partner_form_td_refund_inherit` | `res.partner` | form inherit | `td_partner_short_name`, `use_in_vendor_refund_report` |
| `hr_employee_form__inherit` | `hr.employee` | form inherit | `td_partner_short_name`, `td_driver_license_number` |
| `fleet_vehicle_view_form_ttn_inherit` | `fleet.vehicle` | form inherit | Група "Body Parameters" |
| `td_view_location_form_with_conditions` | `stock.location` | form inherit | Вкладка "Conditions" з `td_condition_ids` |
| `view_td_stock_condition_list` | `td.stock.condition` | list (editable) | Список умов зберігання |
| `action_td_stock_condition` | — | act_window | Відкриває список умов |
| `td_menu_stock_condition` | — | menuitem | Inventory → Configuration → Stock Conditions |

> Поле `td_transport_ownership` на `fleet.vehicle` закоментоване у view (поле є у моделі, але UI не показує його).

---

## Звіти (QWeb PDF)

| XML id дії | Назва | Модель | Paper format | Домен |
|------------|-------|--------|--------------|-------|
| `action_report_wholesale_invoice_picking` | Оптова накладна | `stock.picking` | Portrait A4 | outgoing, `exp_inv` |
| `action_report_wholesale_invoice_invoice` | Оптова накладна | `account.move` | Portrait A4 | `out_invoice`, posted |
| `action_report_ordering_eye_lenses` | Для складу | `stock.picking` | Portrait A4 | outgoing / internal |
| `action_report_warehouse_order` | Для складу (з серіями) | `stock.picking` | Portrait A4 | outgoing / internal |
| `action_report_return_from_stock` | Повернення з переміщення | `stock.picking` | Portrait A4 | incoming, done, return або `move` |
| `action_report_waybill_new` | Товарно-транспортна (ТТН) | `stock.picking` | **Landscape** A4 | outgoing / internal, done |
| `action_report_custody_transfer_act` | Акт передачі на відп. зберігання | `stock.picking` | Portrait A4 | outgoing, `act_res_st` |
| `action_report_custody_return_act` | Акт повернення з відп. зберігання | `stock.picking` | Portrait A4 | incoming, `act_res_st` |
| `action_report_custody_balance` | Акт звірки залишків | `stock.picking` | Portrait A4 | incoming, `act_res_st` |
| `action_report_refund_act_td` | Накладна на повернення | `stock.picking` | Portrait A4 | incoming, return, не `act_res_st`, done |
| `action_report_invoice_act` | Рахунок-фактура | `account.move` | Portrait A4 | `out_invoice`, posted |
| `action_report_commercial_offer` | Комерційна пропозиція | `sale.order` | Portrait A4 | `state != sale` |
| `action_report_commercial_offer_components` | Комерційна пропозиція (компоненти) | `sale.order` | Portrait A4 | `state != sale` |
| `action_report_commercial_offer_inv` | Комерційна пропозиція | `account.move` | Portrait A4 | без domain |
| `action_report_vendor_refund_act` | Повернення постачальнику | `stock.picking` | Portrait A4 | outgoing/internal, done, `purchase_id` |
| `action_report_completion_act` | Акт комплектації | `stock.picking` | Portrait A4 | outgoing/internal, done |

**Paper formats:**
- `td_medicus_paperformat` — Portrait A4, margins top/bottom=10, left/right=0, dpi=90
- `td_medicus_paperformat_landscape` — Landscape A4, аналогічні margins

---

## Зовнішні інтеграції
Відсутні.

## Конфігурація
`ir.config_parameter` не використовуються. Усе налаштовується через `res.company`.

---

## Безпека

| Модель | Група | Read | Write | Create | Delete |
|--------|-------|------|-------|--------|--------|
| `td.stock.condition` | `base.group_user` | ✓ | ✓ | ✓ | ✓ |
| `td.amount.to.words.mixin` | `base.group_user` | ✓ | ✓ | ✓ | ✓ |

> Розширення стандартних моделей успадковують права батьківської моделі.

---

## Технічний борг (Known limitations)

1. **`td_ttn_gross_weight_`** — ім'я поля із зайнім `_` (рефакторинг потребує міграції).
2. **Одне поле ліцензії** — `td_ttn_driver_license_number` спільне для `own`/`hired`; скидається при зміні типу перевезення.
3. **`td_ttn_driver_partner_id` — legacy** — поле є у моделі і onchange, але прихований у view (`invisible="1"`). UI не може його заповнити.
4. **`td_transport_ownership` — неповний UI** — поле на `fleet.vehicle` є, але XPath у view закоментовано.
5. **`REPORT_IDS` в `ir_actions_report.py`** — константа оголошена, але ніде не використовується.
6. **Захардкоджений сертифікат** — `sertificate_number: '35589038'` у `td_get_co_data`.
7. **Дублювання `td_ttn_driver_forwarder`** у view — поле присутнє у обох секціях (own/hired) XML через окремі XPath-гілки.
8. **Закоментований старий код** у `stock_picking.py` — старі поля Float та `_onchange_td_ttn_vehicle_id`.

---

## Відкриті питання
*Всі питання вирішені під час аналізу коду. Специфікація готова до архітектури.*
