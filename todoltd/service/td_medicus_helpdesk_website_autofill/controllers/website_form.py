import logging
import pprint
import re
import unicodedata

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

_INVISIBLES = (
    '\u00a0\u202f\u200b\u200c\u200d\ufeff\u00ad\u2060'
)


def _clean(value):
    if not isinstance(value, str):
        return ''
    value = unicodedata.normalize('NFKC', value)
    value = value.translate({ord(c): None for c in _INVISIBLES})
    value = re.sub(r'\s+', ' ', value).strip()
    return value


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
            v = _clean(src.get(k))
            if v:
                return v
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

        raw_serial = next(
            (values.get(k) for k in _SERIAL_KEYS if values.get(k)), None
        )
        if raw_serial is not None and raw_serial != serial:
            _logger.info(
                "%s serial normalized: raw=%r -> clean=%r",
                _LOG_PREFIX, raw_serial, serial,
            )
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

        lot = self._td_find_lot(env, serial, partner)
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
    def _td_find_lot(env, serial, partner):
        Lot = env['stock.lot'].sudo()

        lot = Lot.search([
            ('name', '=', serial),
            ('last_delivery_partner_id', 'child_of', partner.id),
        ], limit=1)
        if lot:
            return lot

        lot = Lot.search([
            ('name', '=ilike', serial),
            ('last_delivery_partner_id', 'child_of', partner.id),
        ], limit=1)
        if lot:
            _logger.info(
                "%s stage2 lot matched via =ilike fallback (stored name "
                "differs only by case): %r", _LOG_PREFIX, lot.name,
            )
        return lot

    @staticmethod
    def _td_find_lot_report(lot, partner):
        return request.env['stock.lot.report'].sudo().search([
            ('lot_id', '=', lot.id),
            ('partner_id', 'child_of', partner.id),
        ], order='delivery_date desc', limit=1)

    @staticmethod
    def _td_diagnose_lot_miss(serial, partner):
        Lot = request.env['stock.lot'].sudo()
        nearby = Lot.search([('name', 'ilike', serial)], limit=10)
        if not nearby:
            _logger.warning(
                "%s stage2 lot MISS: no stock.lot name even contains %r — "
                "the value is probably not a stock.lot serial at all",
                _LOG_PREFIX, serial,
            )
            return

        _logger.warning(
            "%s stage2 lot MISS for cleaned serial=%r. Lots whose name "
            "CONTAINS it (note exact vs stored difference, and the delivery "
            "partner vs requested partner id=%s): %s",
            _LOG_PREFIX, serial, partner.id,
            [
                (l.id, repr(l.name), l.last_delivery_partner_id.id,
                 l.last_delivery_partner_id.display_name or '<empty>')
                for l in nearby
            ],
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
            "none has partner_id child_of %s. Existing rows: %s",
            _LOG_PREFIX, lot.id, partner.id,
            [
                (r.id, r.partner_id.id, r.partner_id.display_name,
                 str(r.delivery_date))
                for r in all_rows
            ],
        )