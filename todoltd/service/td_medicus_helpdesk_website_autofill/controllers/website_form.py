import logging
import pprint

from odoo.http import request
from odoo.addons.website.controllers.form import WebsiteForm

_logger = logging.getLogger(__name__)
_LOG_PREFIX = "[td_autofill]"


_EDRPOU_KEYS = (
    'ЄРДПОУ',
    'ЄДРПОУ',
    'company_registry',
    'edrpou',
    'x_edrpou',
    'td_edrpou',
    'l10n_ua_edrpou',
)

_SERIAL_KEYS = (
    'Серійний номер обладнання',
    'serial_number',
    'sn',
    's_n',
    'serial',
    'x_serial_number',
    'td_serial_number',
    'td_serial_number_id',
)

_PROTECTED_KEYS = ('partner_id', 'td_equipment_id', 'td_serial_number_id')


class WebsiteFormAutofill(WebsiteForm):

    def extract_data(self, model, values):
        sanitized = dict(values)
        dropped = {k: sanitized.pop(k) for k in _PROTECTED_KEYS if k in sanitized}
        if dropped:
            _logger.warning(
                "%s dropping client-supplied protected fields: %s",
                _LOG_PREFIX, dropped,
            )

        data = super().extract_data(model, sanitized)

        if model and model.model == 'helpdesk.ticket':
            try:
                self._td_autofill_helpdesk(values, data)
            except Exception:
                _logger.exception(
                    "%s lookup failed, submission continues without auto-fill",
                    _LOG_PREFIX,
                )
        return data

    @staticmethod
    def _td_first(src, keys):
        for k in keys:
            v = src.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ''

    def _td_autofill_helpdesk(self, values, data):
        loggable = {
            k: (v[:120] + '…') if isinstance(v, str) and len(v) > 120 else v
            for k, v in values.items()
        }
        _logger.info(
            "%s incoming form payload (%d keys): %s",
            _LOG_PREFIX, len(values), pprint.pformat(loggable, width=120),
        )

        edrpou = self._td_first(values, _EDRPOU_KEYS)
        serial = self._td_first(values, _SERIAL_KEYS)
        _logger.info(
            "%s extracted edrpou=%r serial=%r", _LOG_PREFIX, edrpou, serial,
        )

        if not edrpou and not serial:
            _logger.info(
                "%s no edrpou and no serial in payload — nothing to do",
                _LOG_PREFIX,
            )
            return

        env = request.env
        record = data.setdefault('record', {})

        partner = env['res.partner'].browse()
        if edrpou:
            partner = env['res.partner'].sudo().search([
                ('company_registry', '=', edrpou),
                ('parent_id', '=', False),
            ], limit=1)
            if partner:
                _logger.info(
                    "%s stage1 OK: partner id=%s name=%r matched on "
                    "company_registry=%r",
                    _LOG_PREFIX, partner.id, partner.display_name, edrpou,
                )
                record['partner_id'] = partner.id
            else:
                any_match = env['res.partner'].sudo().search([
                    ('company_registry', '=', edrpou),
                ], limit=5)
                if any_match:
                    _logger.warning(
                        "%s stage1 MISS for edrpou=%r as parent contact, but "
                        "matches exist as child contacts: %s — fix the data "
                        "(EDRPOU should be on the parent res.partner) or "
                        "broaden the lookup",
                        _LOG_PREFIX, edrpou,
                        [(p.id, p.display_name, p.parent_id.id) for p in any_match],
                    )
                else:
                    _logger.warning(
                        "%s stage1 MISS: no res.partner has company_registry=%r",
                        _LOG_PREFIX, edrpou,
                    )
        else:
            _logger.info("%s stage1 skipped: no edrpou in payload", _LOG_PREFIX)

        if not (partner and serial):
            _logger.info(
                "%s stage2 skipped: partner=%s serial=%r",
                _LOG_PREFIX, partner.id if partner else None, serial,
            )
            return

        lot = env['stock.lot'].sudo().search([
            ('name', '=', serial),
            ('last_delivery_partner_id', '=', partner.id),
        ], limit=1)

        if not lot:
            self._td_diagnose_lot_miss(serial, partner)
            return

        _logger.info(
            "%s stage2 lot OK: lot id=%s name=%r product=%r "
            "last_delivery_partner_id=%s",
            _LOG_PREFIX, lot.id, lot.name,
            lot.product_id.display_name,
            lot.last_delivery_partner_id.id,
        )

        report_rec = self._td_find_lot_report(lot, partner)
        if not report_rec:
            self._td_diagnose_report_miss(lot, partner)
            return

        _logger.info(
            "%s stage2 report OK: stock.lot.report id=%s "
            "lot_id=%s partner_id=%s delivery_date=%s",
            _LOG_PREFIX, report_rec.id, report_rec.lot_id.id,
            report_rec.partner_id.id, report_rec.delivery_date,
        )

        record['td_equipment_id'] = report_rec.id
        record['td_serial_number_id'] = report_rec.id

        _logger.info(
            "%s final auto-fill written to data['record']: "
            "partner_id=%s td_equipment_id=%s td_serial_number_id=%s",
            _LOG_PREFIX,
            record.get('partner_id'),
            record.get('td_equipment_id'),
            record.get('td_serial_number_id'),
        )

    @staticmethod
    def _td_diagnose_lot_miss(serial, partner):
        Lot = request.env['stock.lot'].sudo()
        candidates = Lot.search([('name', '=', serial)], limit=10)
        if not candidates:
            _logger.warning(
                "%s stage2 lot MISS: no stock.lot with name=%r exists at all",
                _LOG_PREFIX, serial,
            )
            return

        rows = [
            (
                lot.id,
                lot.product_id.display_name,
                lot.last_delivery_partner_id.id,
                lot.last_delivery_partner_id.display_name or '<empty>',
                lot.last_delivery_partner_id.parent_id.id or None,
            )
            for lot in candidates
        ]
        _logger.warning(
            "%s stage2 lot MISS for (name=%r, last_delivery_partner_id=%s). "
            "Lots with that serial exist but with a different / empty "
            "delivery partner: %s",
            _LOG_PREFIX, serial, partner.id, rows,
        )

        children_of_partner = [r for r in rows if r[4] == partner.id]
        if children_of_partner:
            _logger.warning(
                "%s HINT: those lots were delivered to a CHILD contact of "
                "partner id=%s (name=%r). The strict match on the parent "
                "partner intentionally rejects this. Either move the EDRPOU "
                "delivery to the parent contact, or relax the stage2 domain "
                "to include children.",
                _LOG_PREFIX, partner.id, partner.display_name,
            )

    @staticmethod
    def _td_diagnose_report_miss(lot, partner):
        Report = request.env['stock.lot.report'].sudo()
        all_rows = Report.search([('lot_id', '=', lot.id)])
        if not all_rows:
            _logger.warning(
                "%s stage2 report MISS: no stock.lot.report rows exist for "
                "lot id=%s. The lot's `last_delivery_partner_id` is set, but "
                "the SQL view sees no qualifying outgoing stock_move_line — "
                "check the picking type code (must be 'outgoing') and that "
                "the move is in state='done'.",
                _LOG_PREFIX, lot.id,
            )
            return

        _logger.warning(
            "%s stage2 report MISS: report rows for lot id=%s exist, but "
            "none has partner_id=%s. Existing rows: %s",
            _LOG_PREFIX, lot.id, partner.id,
            [
                (r.id, r.partner_id.id, r.partner_id.display_name,
                 r.partner_id.parent_id.id or None,
                 str(r.delivery_date))
                for r in all_rows
            ],
        )

    @staticmethod
    def _td_find_lot_report(lot, partner):
        return request.env['stock.lot.report'].sudo().search([
            ('lot_id', '=', lot.id),
            ('partner_id', '=', partner.id),
        ], order='delivery_date desc', limit=1)
