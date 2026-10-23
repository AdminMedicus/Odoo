# Module: td_medicus_equipment_partner

## Status
<!-- draft | review | approved | superseded -->
approved

## Methodology
tdd

## Version history
| Date | Author | Change |
|------|--------|--------|
| 2026-10-19 | spec-writer AI | Initial spec: ТЗ 20 «Доопрацювання сценарію авто заповнення клієнта, якщо клієнт не є покупцем об-ння» + узгоджена схема (власник на серійнику, таблиця заявників), обидві черги |
| 2026-10-19 | developer | `td_last_delivery_partner_id` не чіпаємо: власник лише у власному полі `td_owner_id`, колонка «Last Delivered To» лишається; статус → approved |
| 2026-10-19 | code-dev AI | TDD-цикл AC-01…AC-38 зелений (63 тести); `td_owner_id` і `td_applicant_edrpou` заявки — явні поля замість stored compute (надійне «заморожування» закритих заявок); додано `td_owner_edrpou` для банера |
| 2026-10-20 | developer | AC-40: пізно створений контрагент стає й клієнтом заявок свого заявника (`ticket_ids`) без клієнта |
| 2026-10-23 | developer | AC-16: пошук серійника лише точний (`=`), без запасного `=ilike` без урахування регістру |

## Odoo version
18.0

## Category
Services / Helpdesk

## Business purpose
Зараз заявка визначає обладнання через клієнта: ЄДРПОУ → клієнт → серійники, відвантажені
саме цьому клієнту. Коли обладнання купила компанія А, а звертається компанія Б, ланцюжок рветься:
серійник не знаходиться, і інженер не бачить, що заявник не є покупцем. Модуль робить клієнта
(платника, за ЄДРПОУ) і обладнання (за серійним номером) незалежними, зберігає власника на картці
серійного номера, показує позначку «Не власник» і веде таблицю «Заявники обладнання»: хто й скільки
разів звертався щодо кожного серійника, з підтвердженням інженера. Документи (ремонт, КП, рахунок,
видаткова накладна, «Замовник» сервісного звіту) завжди йдуть на клієнта заявки.

Перша черга: AC-01 … AC-27 (ТЗ п. 1–5 і поле «Власник»).
Друга черга: AC-28 … AC-40 (таблиця «Заявники обладнання»).

## User stories

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US-01 | Inventory / User (проведення накладних) | щоб власник серійника визначався з видаткових накладних | система знала покупця обладнання без ручного введення |
| US-02 | Helpdesk / User (інженер) | обирати обладнання й серійний номер у заявці без обмеження клієнтом | заявку щодо чужого обладнання можна оформити повністю |
| US-03 | Helpdesk / User | бачити на заявці й канбані, що заявник не є власником | не помилитися з договором, рахунком і підписантом |
| US-04 | Helpdesk / Manager | відфільтрувати всі заявки, де заявник ≠ власник | переглянути такі звернення окремо |
| US-05 | Website visitor (через веб-форму) | щоб заявка з форми отримала клієнта за ЄДРПОУ й обладнання за серійником незалежно | заявка заповнювалась і тоді, коли я не покупець обладнання |
| US-06 | Helpdesk / User | змінювати «Замовника» сервісного звіту і бачити договори клієнта першими | звіт і договір відповідали фактичному платнику |
| US-07 | Helpdesk / User | щоб ремонт і документи з заявки оформлювались на клієнта заявки | рахунок не пішов покупцю обладнання |
| US-08 | Helpdesk / User | щоб система вела заявників по кожному серійнику і давала їх підтвердити | повторні звернення відомого заявника не виглядали як тривога |
| US-09 | Helpdesk / Manager | змінити власника серійника із заявки чи картки | врахувати перепродаж обладнання поза Medicus |
| US-10 | Helpdesk / User | знайти серійники, які вже обслуговувалися для клієнта | швидко обрати потрібне обладнання в заявці |

## Acceptance criteria

### Перша черга — власник на серійнику

- **AC-01** [US-01]: Given серійний лот L товару з `tracking = 'serial'` і вихідне переміщення
  (`picking_type_code = 'outgoing'`) з `implementation_document` `'exp_inv'` або порожнім,
  партнер якого — контакт C компанії A, when переміщення проведено (`button_validate`),
  then `L.td_owner_id == A` (комерційний партнер C).
- **AC-02** [US-01]: Given лот L з власником A (або без власника) і вихідне переміщення з
  `implementation_document` `'act_res_st'` або `'move'`, when переміщення проведено,
  then `L.td_owner_id` не змінився.
- **AC-03** [US-01]: Given лот L з власником A, when проведено продаж L компанії E (як в AC-01),
  then `L.td_owner_id == E` і в чаті L є повідомлення трекінгу поля «Owner» зі зміною A → E.
- **AC-04** [US-01]: Given лот L з власником A, встановленим продажем D, when проведено повернення
  D (`return_id = D`) з лотом L, then `L.td_owner_id` порожній; якщо до повернення власник
  уже став E ≠ A, then власник лишається E.
- **AC-05** [US-01]: Given проведені до встановлення модуля продажі й повернення лотів, when
  виконується `stock.lot._td_backfill_owners()` (викликається з `post_init_hook`), then власник
  кожного лота дорівнює результату послідовного застосування AC-01…AC-04 за `date_done`.
- **AC-06** [US-09]: Given користувач без груп `helpdesk.group_helpdesk_manager` і
  `stock.group_stock_manager`, when він записує `td_owner_id` лота, then `AccessError`;
  given користувач з `helpdesk.group_helpdesk_manager`, then значення зберігається.

### Перша черга — поля заявки

- **AC-07** [US-02]: Given поле `helpdesk.ticket.product_id`, then його домен дорівнює
  `[('tracking', '!=', 'none')]` і не містить `suitable_product_ids`; given заявка з клієнтом B,
  when у формі (`Form`) вибрано товар P, який B ніколи не продавали, then після збереження
  `ticket.product_id == P`.
- **AC-08** [US-02]: Given заявка без `product_id`, when домен поля `lot_id` обчислено для неї,
  then пошук за ним повертає лоти різних товарів; given заявка з товаром P, then лише лоти P.
- **AC-09** [US-02]: Given форма заявки, when вибрано лот L, then `product_id == L.product_id`;
  when після цього змінено клієнта, then `product_id` і `lot_id` не змінились; when змінено товар
  на інший, then `lot_id` порожній.
- **AC-10** [US-02]: Given заявка з `td_serial_number_id` (рядок `stock.lot.report` лота L) і
  порожнім `lot_id`, when виконується `helpdesk.ticket._td_migrate_equipment_fields()` (з
  `post_init_hook`), then `lot_id == L` і `product_id == L.product_id`.

### Перша черга — позначка «Не власник»

- **AC-11** [US-03]: Given лот L з власником A, when у заявці `lot_id = L` і клієнт — контакт
  компанії B, then `td_owner_id == A` і `td_is_not_owner is True`; when клієнт — контакт компанії
  A, then `td_is_not_owner is False`; when L без власника, then `td_owner_id` порожній і
  `td_is_not_owner is False`.
- **AC-12** [US-03]: Given відкрита заявка (стадія не `fold`) з лотом L власника A, when власник L
  змінився на E, then `ticket.td_owner_id == E`; given заявка у стадії з `fold = True`, then
  `td_owner_id` і `td_is_not_owner` лишаються попередніми.
- **AC-13** [US-03]: Given заявка з `td_is_not_owner is True` і без підтвердженого заявника,
  then `td_owner_notice == 'warning'`; given `td_is_not_owner is False`, then `'none'`.
- **AC-14** [US-04]: Given пошуковий вид заявок (`get_view(view_type='search')`), then він містить
  фільтр `td_filter_not_owner` з доменом `[('td_is_not_owner', '=', True)]`.
- **AC-15** [US-03] [manual]: На формі заявки над полями — жовтий банер «Обладнання придбане іншою
  компанією: {власник} (ЄДРПОУ {код}). Перевірте договір обслуговування та платника.»; на картці
  канбану — бейдж «Not owner» поруч із мітками; банер не заважає збереженню і зміні стадії.

### Перша черга — веб-форма

- **AC-16** [US-05]: Given серійник S, що відповідає рівно одному лоту L (точний збіг з
  урахуванням регістру і нулів на початку; зайві пробіли й невидимі символи навколо
  прибираються; інший регістр лот не знаходить), і ЄДРПОУ компанії B,
  when `helpdesk.ticket._td_autofill_values(values)` обробляє значення форми, then результат
  містить `partner_id = B`, `lot_id = L`, `product_id = L.product_id`; заявка, створена з ними,
  при власнику A має `td_is_not_owner is True`.
- **AC-17** [US-05]: Given серійник знайдено, а ЄДРПОУ немає в базі, when обробляється форма,
  then результат містить `lot_id` і `product_id` без `partner_id`, і кількість `res.partner`
  не змінилась.
- **AC-18** [US-05]: Given ЄДРПОУ знайдено, а серійника немає, then результат містить лише
  `partner_id`.
- **AC-19** [US-05]: Given серійник S збігається з лотами L1 (товар P1) і L2 (товар P2), when
  власник L1 — компанія клієнта з ЄДРПОУ, then `lot_id = L1`; when жоден лот не пов'язаний із
  клієнтом, then `lot_id` відсутній, а `custom`-рядки результату містять «P1 — S» і «P2 — S».
- **AC-20** [US-05]: Given значення форми з ключами `partner_id`, `product_id`, `lot_id`,
  `td_applicant_id`, `td_applicant_edrpou`, when контролер їх очищає
  (`_td_sanitize_values`), then жодного з цих ключів у результаті немає.

### Перша черга — сервісний звіт

- **AC-21** [US-06]: Given заявка з клієнтом B, when створено сервісний звіт, then
  `report.partner_id == B`; when звіт змінено на клієнта C, then значення збережено, а в чаті
  заявки з'явилась нотатка з підписом поля «Customer» і зміною B → C.
- **AC-22** [US-06]: Given звіт із «Замовником» B, when клієнта заявки змінено на C, then
  `report.partner_id` лишається B.
- **AC-23** [US-06]: Given заявка з `lot_id = L`, when створюється звіт (через `default_get` і
  через `create` без `td_lot_id`), then `report.td_lot_id == L`.
- **AC-24** [US-06]: Given заявка з лотом L і клієнтом B, then її `td_agreement_domain` вибирає
  договори, прив'язані до L, і договори B; when у формі вибрано L, then `td_agreement_ids`
  дорівнює договорам L.
- **AC-25** [US-06]: Given договори X (B, прив'язаний до L), Y (B, не прив'язаний), Z (інший
  контрагент, прив'язаний до L), when `td.agreement.name_search` виконується з доменом заявки і
  контекстом `td_agreement_client_id = B`, then порядок результатів X, Y, Z, а `display_name`
  кожного в цьому контексті закінчується « — {назва контрагента}».

### Перша черга — ремонт і документи

- **AC-26** [US-07]: Given заявка з клієнтом B і лотом L власника A, when викликано
  `_prepare_repairs_default_value()`, then `default_partner_id == B`, `default_lot_id == L`,
  `default_product_id == L.product_id`.
- **AC-27** [US-07]: Given ремонт, створений із цими значеннями, when викликано
  `action_create_sale_order()`, then `sale_order_id.partner_id == B`.

### Друга черга — заявники обладнання

- **AC-28** [US-08]: Given заявка з лотом L і клієнтом — контактом компанії B (ЄДРПОУ
  `12345678`), when заявку створено, then існує `td.equipment.applicant` (L, `12345678`,
  partner B, `is_confirmed False`) і `ticket.td_applicant_id` вказує на нього; when створено другу
  заявку для L і B, then використано той самий запис і `ticket_count == 2`.
- **AC-29** [US-08]: Given форма з серійником лота L і ЄДРПОУ `87654321`, якого немає в базі,
  when створено заявку, then `td_applicant_edrpou == '87654321'`, запис заявника має
  `company_name` = заголовок заявки, `contact_name` = `partner_name`, `phone` = `partner_phone`,
  порожній `partner_id`; при власнику L з іншим ЄДРПОУ `td_is_not_owner is True`.
- **AC-30** [US-08]: Given заявка без клієнта з `td_applicant_edrpou`, що не складається з 8 або
  10 цифр, then запис заявника не створюється; when запис без `partner_id` створюється з таким
  ЄДРПОУ напряму, then `ValidationError`.
- **AC-31** [US-08]: Given запис (L, `12345678`), when створюється другий запис (L, `12345678`),
  then `ValidationError`.
- **AC-32** [US-08]: Given записи заявника з ЄДРПОУ `87654321` без партнера, when створено або
  змінено партнера верхнього рівня з `company_registry = '87654321'`, then їхній `partner_id`
  дорівнює цьому партнеру.
- **AC-33** [US-08]: Given заявка з лотом L і заявником (L, B), when лот змінено на L2, then
  `td_applicant_id` вказує на запис (L2, B), створений за потреби, а запис (L, B) лишається.
- **AC-34** [US-08]: Given заявка з `td_is_not_owner is True`, when інженер викликає
  `action_td_confirm_applicant()`, then `is_confirmed is True`, заповнені `confirmed_uid` і
  `confirmed_date`, `td_owner_notice == 'info'`, а `td_is_not_owner` лишається `True`.
- **AC-35** [US-09]: Given заявка з клієнтом B і лотом власника A, when користувач з
  `helpdesk.group_helpdesk_manager` викликає `action_td_make_owner()`, then `L.td_owner_id == B`,
  `td_is_not_owner is False`, `td_owner_notice == 'none'`; when викликає користувач без груп
  менеджера, then `AccessError`; given заявка без клієнта, then `UserError`.
- **AC-36** [US-10]: Given лоти L1 (є заявник B), L2 (власник B), L3 (не пов'язаний із B), when
  шукати `stock.lot` з доменом `[('td_serviced_for_client', '=', True)]` і контекстом
  `td_client_id = B`, then результат містить L1 і L2 і не містить L3.
- **AC-37** [US-08]: Given заявки, створені до встановлення модуля, з лотом і клієнтом, when
  виконується `helpdesk.ticket._td_backfill_applicants()` (з `post_init_hook`), then кожна з них
  має `td_applicant_id` на непідтверджений запис відповідної пари.
- **AC-38** [US-08]: Given користувач `helpdesk.group_helpdesk_user`, then він може створити й
  змінити запис заявника, а видалення дає `AccessError`; користувач
  `helpdesk.group_helpdesk_manager` видаляє запис успішно.
- **AC-40** [US-08]: Given заявник з ЄДРПОУ `87654321` без партнера і його заявки без клієнта
  (відкриті й закриті), when створено партнера верхнього рівня з
  `company_registry = '87654321'` або цей код записано наявному партнеру верхнього рівня, then
  разом із заявником (AC-32) `partner_id` його заявок без клієнта дорівнює цьому партнеру;
  заявки інших заявників і заявки, де клієнт уже вказаний, не змінюються. Заявки без серійника
  (без запису заявника) так не оновлюються.
- **AC-39** [US-08] [manual]: На картці серійника — поле «Owner» і вкладка «Applicants»; у списку
  серійників додано колонку «Owner» (колонка «Last Delivered To» лишається без змін); на заявці для підтвердженого заявника —
  інформаційний рядок замість жовтого банера; кнопка «Confirm Applicant» видна інженеру, кнопка
  «Make Owner» — лише менеджеру; меню Helpdesk / Configuration / Equipment Applicants.

## Models

### StockLot (`stock.lot`) — extension
Since: `18.0.1.0.0`

Поле власника належить лоту: власник — властивість конкретної одиниці обладнання, а не заявки.
Це власне поле модуля; наявне `td_last_delivery_partner_id` (`td_medicus_warranty`) не
змінюється і логікою власника не використовується.

**Fields:**
| Field | Type | Required | Default | Since | Description |
|-------|------|----------|---------|-------|-------------|
| td_owner_id | Many2one → `res.partner` | No | — | 18.0.1.0.0 | Owner: компанія-покупець; `tracking=True`, `index=True`; пишеться логікою накладних і менеджерами |
| td_applicant_ids | One2many → `td.equipment.applicant` (`lot_id`) | No | — | 18.0.1.0.0 | Applicants (друга черга) |
| td_serviced_for_client | Boolean (не stored, `search=`) | No | — | 18.0.1.0.0 | Для фільтра «Serviced for this client»: шукає за контекстом `td_client_id` |

**Key methods:**
| Method | Trigger | Since | Description |
|--------|---------|-------|-------------|
| `write` (override) | ORM | 18.0.1.0.0 | AC-06: зміна `td_owner_id` лише для менеджерів, крім автоматичних оновлень (`sudo`/контекст) |
| `_td_backfill_owners` | `post_init_hook` | 18.0.1.0.0 | AC-05 |
| `_search_td_serviced_for_client` | search | 18.0.1.0.0 | AC-36 |

### StockPicking (`stock.picking`) — extension
Since: `18.0.1.0.0`

**Key methods:**
| Method | Trigger | Since | Description |
|--------|---------|-------|-------------|
| `_action_done` (override) | Проведення | 18.0.1.0.0 | AC-01…AC-04: оновлює `td_owner_id` лотів продажу й повернення |

### HelpdeskTicket (`helpdesk.ticket`) — extension
Since: `18.0.1.0.0`

`product_id` і `lot_id` — стандартні поля `helpdesk_stock`; на формі мають підписи «Equipment» і
«Serial Number» і замінюють поля `td_equipment_id` / `td_serial_number_id` (вони ховаються, дані
переносяться за AC-10). Стандартна кнопка «Ремонт» уже передає ці поля в ремонт.

**Fields:**
| Field | Type | Required | Default | Since | Description |
|-------|------|----------|---------|-------|-------------|
| product_id | Many2one (override) | No | — | 18.0.1.0.0 | Домен `[('tracking', '!=', 'none')]` (AC-07) |
| lot_id | Many2one (override) | No | — | 18.0.1.0.0 | Домен `[('product_id', '=?', product_id)]` (AC-08) |
| td_owner_id | Many2one → `res.partner` | No | — | 18.0.1.0.0 | Equipment Owner, readonly: копія власника лота; оновлюється під час створення заявки і зміни `lot_id`, а при зміні власника лота — лише у відкритих заявках (стадія не `fold`) (AC-11, AC-12) |
| td_applicant_edrpou | Char | No | — | 18.0.1.0.0 | Applicant EDRPOU: з форми або вручну; при виборі клієнта перезаписується його `company_registry` (`create` / `write` / onchange) |
| td_applicant_id | Many2one → `td.equipment.applicant` | No | — | 18.0.1.0.0 | Applicant (друга черга), readonly |

**Computed fields:**
| Field | Depends on | Stored | Since | Description |
|-------|-----------|--------|-------|-------------|
| td_is_not_owner | `td_owner_id`, `partner_id.commercial_partner_id`, `td_applicant_edrpou` | Yes | 18.0.1.0.0 | Not Owner: власник є і компанія клієнта (або ЄДРПОУ заявника без клієнта) інша |
| td_owner_notice | `td_is_not_owner`, `td_applicant_id.is_confirmed` | No | 18.0.1.0.0 | Selection `none` / `warning` / `info` (AC-13, AC-34) |
| td_owner_edrpou | related `td_owner_id.company_registry` | No | 18.0.1.0.0 | Owner EDRPOU для тексту банера (AC-15) |

**Key methods:**
| Method | Trigger | Since | Description |
|--------|---------|-------|-------------|
| `_td_autofill_values(values)` | `@api.model`, з контролера форми | 18.0.1.0.0 | AC-16…AC-19: повертає `{'record': {...}, 'custom': [...]}` |
| `_onchange_lot_id_td` / `_onchange_product_id_td` | onchange | 18.0.1.0.0 | AC-09 |
| `onchange_product_id` (override helpdesk_stock) | onchange | 18.0.1.0.0 | AC-09: не очищує товар при зміні клієнта |
| `_compute_td_agreement_domain` (override) | compute | 18.0.1.0.0 | AC-24: лот із `lot_id` + договори клієнта |
| `_td_sync_applicant` | `create` / `write` | 18.0.1.0.0 | AC-28, AC-29, AC-33 |
| `action_td_confirm_applicant` | Кнопка | 18.0.1.0.0 | AC-34 |
| `action_td_make_owner` | Кнопка | 18.0.1.0.0 | AC-35 |
| `_td_migrate_equipment_fields` | `post_init_hook` | 18.0.1.0.0 | AC-10 |
| `_td_backfill_applicants` | `post_init_hook` | 18.0.1.0.0 | AC-37 |

### TdServiceReport (`td.service.report`) — extension
Since: `18.0.1.0.0`

**Fields:**
| Field | Type | Required | Default | Since | Description |
|-------|------|----------|---------|-------|-------------|
| partner_id | Many2one → `res.partner` (override) | No | клієнт заявки при створенні | 18.0.1.0.0 | Customer: більше не `related`; редагується; `tracking=True` → нотатка в чаті заявки (AC-21, AC-22) |

**Key methods:**
| Method | Trigger | Since | Description |
|--------|---------|-------|-------------|
| `default_get` / `create` (override) | ORM | 18.0.1.0.0 | AC-23: `td_lot_id` з `ticket.lot_id` |
| `_compute_td_agreement_domain` (override) | compute | 18.0.1.0.0 | AC-24 для звіту: лот звіту + договори «Замовника» |

### TdAgreement (`td.agreement`) — extension
Since: `18.0.1.0.0`

**Key methods:**
| Method | Trigger | Since | Description |
|--------|---------|-------|-------------|
| `_name_search` (override) | name_search | 18.0.1.0.0 | AC-25: з контекстом `td_agreement_client_id` — спершу договори клієнта, прив'язані до лота, далі інші договори клієнта, далі решта |
| `_compute_display_name` (override) | compute | 18.0.1.0.0 | AC-25: у тому ж контексті додає « — {контрагент}» |

### ResPartner (`res.partner`) — extension
Since: `18.0.1.0.0`

**Key methods:**
| Method | Trigger | Since | Description |
|--------|---------|-------|-------------|
| `create` / `write` (override) | ORM | 18.0.1.0.0 | AC-32: підв'язує записи заявників з таким самим ЄДРПОУ; AC-40: стає клієнтом заявок цих заявників (`ticket_ids`) без клієнта |

### Equipment Applicant (`td.equipment.applicant`)
Inherits: `mail.thread`, `mail.activity.mixin`
Since: `18.0.1.0.0`

Один запис на пару «серійник + ЄДРПОУ» (або «серійник + партнер», коли в партнера немає коду).
Створюється автоматично із заявки; контрагент при цьому не створюється.

**Fields:**
| Field | Type | Required | Default | Since | Description |
|-------|------|----------|---------|-------|-------------|
| lot_id | Many2one → `stock.lot` | Yes | — | 18.0.1.0.0 | Serial Number, `ondelete='cascade'`, `index=True` |
| product_id | Many2one → `product.product` | No | — | 18.0.1.0.0 | Equipment, related `lot_id.product_id`, stored |
| edrpou | Char | No | — | 18.0.1.0.0 | EDRPOU; з `partner_id.company_registry` або введений; `index=True` |
| partner_id | Many2one → `res.partner` | No | — | 18.0.1.0.0 | Partner: компанія, якщо вона є в базі |
| company_name | Char | No | — | 18.0.1.0.0 | Company Name з форми або партнера |
| contact_name | Char | No | — | 18.0.1.0.0 | Contact |
| phone | Char | No | — | 18.0.1.0.0 | Phone |
| ticket_ids | One2many → `helpdesk.ticket` (`td_applicant_id`) | No | — | 18.0.1.0.0 | Tickets |
| is_confirmed | Boolean | No | False | 18.0.1.0.0 | Confirmed, `tracking=True` |
| confirmed_uid | Many2one → `res.users` | No | — | 18.0.1.0.0 | Confirmed By |
| confirmed_date | Datetime | No | — | 18.0.1.0.0 | Confirmed On |

**Computed fields:**
| Field | Depends on | Stored | Since | Description |
|-------|-----------|--------|-------|-------------|
| ticket_count | `ticket_ids` | No | 18.0.1.0.0 | Кількість заявок |
| display_name | `company_name`, `edrpou`, `lot_id` | No | 18.0.1.0.0 | «{компанія} ({ЄДРПОУ}) — {серійник}» |

**Constraints:**
- AC-30: без `partner_id` поле `edrpou` має складатися з 8 або 10 цифр (`ValidationError`).
- AC-31: унікальність (`lot_id`, `edrpou`) для непорожнього `edrpou` і (`lot_id`, `partner_id`) для
  порожнього (`ValidationError`).

**Key methods:**
| Method | Trigger | Since | Description |
|--------|---------|-------|-------------|
| `_td_find_or_create(lot, partner, edrpou, vals)` | `@api.model` | 18.0.1.0.0 | Повертає наявний запис пари або створює новий |

## Views & menus

| Menu path | View types | Access group | Since |
|-----------|-----------|--------------|-------|
| Helpdesk / Configuration / Equipment Applicants | list, form, search | helpdesk.group_helpdesk_manager | 18.0.1.0.0 |
| Форма заявки: банер, поля Equipment / Serial Number / Equipment Owner / Applicant, кнопки | form (inherit) | helpdesk.group_helpdesk_user | 18.0.1.0.0 |
| Канбан заявок: бейдж «Not owner» | kanban (inherit) | helpdesk.group_helpdesk_user | 18.0.1.0.0 |
| Пошук заявок: фільтр «Applicant ≠ Owner», групування за власником | search (inherit) | helpdesk.group_helpdesk_user | 18.0.1.0.0 |
| Картка / список / пошук серійника: Owner, вкладка Applicants, фільтри | form, list, search (inherit) | stock.group_stock_user | 18.0.1.0.0 |
| Сервісний звіт: «Замовник» редагований | form (inherit) | helpdesk.group_helpdesk_user | 18.0.1.0.0 |

## Business logic

### Власник серійника
- Продаж: вихідне переміщення з `implementation_document` `exp_inv` або порожнім → власник =
  комерційний партнер переміщення. Так само обмін з 1С трактує ці переміщення як продаж.
- Акт відповідального зберігання (`act_res_st`) і переміщення (`move`) власника не змінюють.
- Повернення продажу (`return_id` = продаж) очищує власника, якщо він досі той самий.
- Ручна зміна — лише `helpdesk.group_helpdesk_manager` і `stock.group_stock_manager`; кожна зміна
  видна в чаті серійника (трекінг).

### Обробка веб-форми
Серійник і ЄДРПОУ шукаються незалежно. Серійник: лише точний збіг назви лота (`=`, з урахуванням
регістру, без `ilike`) після нормалізації введеного значення (NFKC, невидимі символи, пробіли — як у
`td_medicus_helpdesk_website_autofill`). ЄДРПОУ: `company_registry` серед партнерів без
`parent_id`. Кілька лотів з однією назвою: обирається той, чий власник або заявник пов'язаний із
клієнтом, інакше лот не заповнюється і варіанти йдуть у блок «Інша інформація» опису. Заявка
створюється завжди; партнери й лоти не створюються.

### Позначка «Не власник»
`td_is_not_owner` = власник є і компанія клієнта ≠ власник; без клієнта — ЄДРПОУ заявника ≠ ЄДРПОУ
власника. `td_owner_notice`: `warning` — не власник і заявник не підтверджений; `info` — не
власник, заявник підтверджений; `none` — інакше. Нічого не блокує.

### Заявники обладнання
Запис створюється або перевикористовується, коли в заявці є лот і ідентичність заявника: клієнт
(ЄДРПОУ = його `company_registry`) або коректний `td_applicant_edrpou`. Коли контрагент із таким
ЄДРПОУ з'являється пізніше, він стає партнером записів заявника (AC-32) і клієнтом їхніх заявок,
де клієнта ще немає (AC-40). Підтверджує інженер
кнопкою на заявці; «Make Owner» доступна менеджеру й переносить власника на клієнта заявки.

### Automation rules
None

### Scheduled actions
None

## External integrations
None (контролер веб-форми — розширення `td_medicus_helpdesk_website_autofill`).

## Configuration
None

## Security

| Model | Group | Read | Write | Create | Delete | Since |
|-------|-------|------|-------|--------|--------|-------|
| `td.equipment.applicant` | `stock.group_stock_user` | ✓ | ✗ | ✗ | ✗ | 18.0.1.0.0 |
| `td.equipment.applicant` | `helpdesk.group_helpdesk_user` | ✓ | ✓ | ✓ | ✗ | 18.0.1.0.0 |
| `td.equipment.applicant` | `helpdesk.group_helpdesk_manager` | ✓ | ✓ | ✓ | ✓ | 18.0.1.0.0 |

Зміна `stock.lot.td_owner_id` вручну — `helpdesk.group_helpdesk_manager` або
`stock.group_stock_manager` (перевірка в `write`, AC-06).

**Custom groups defined by this module:**
None

## Reports
None (друкована форма сервісного звіту вже бере `partner_id` звіту).

## Data & demo
`post_init_hook`: перенесення полів заявок (AC-10), власники з історії накладних (AC-05),
заявники з наявних заявок (AC-37).

## Out of scope
- Імпорт обладнання, проданого до запуску Odoo (питання 3 до замовника) — окрема задача.
- Поле `td_last_delivery_partner_id` модуля `td_medicus_warranty` і його колонка «Last Delivered To» не змінюються й не використовуються; власник зберігається лише в новому полі `td_owner_id`.
- Зміни гарантії, прив'язки договорів до серійників, автоматичне створення контрагентів.
- Запис заявника, коли серійник не знайдено (дані лишаються в описі заявки).
- Мультикомпанійні правила (у базі одна компанія).
- Окремі поля «ЄДРПОУ з форми» / «Серійний номер з форми», крім `td_applicant_edrpou`.

## Open questions
- (немає — відкриті питання до замовника закриті нашими пропозиціями, див. нижче)

### Рішення за замовчуванням (до підтвердження замовником)
- П. 5 ТЗ (обрізане речення) — мається на увазі клієнт заявки.
- Відповідальне зберігання — власника не створює, банера немає.
- Договори клієнта, не прив'язані до серійника, показуються після прив'язаних.
- Заявника підтверджує інженер; власника змінюють менеджер сервісу та склад.
- «Замовник» звіту не змінюється слідом за клієнтом заявки.

## Dependencies
```python
'depends': [
    'helpdesk_stock',
    'helpdesk_repair',
    'td_medicus_agreement',
    'td_medicus_helpdesk_website_autofill',
    'td_medicus_service_report',
],
```
