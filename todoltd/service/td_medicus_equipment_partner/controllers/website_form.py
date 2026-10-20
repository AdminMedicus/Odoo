# -*- coding: utf-8 -*-
from odoo.http import request

from odoo.addons.td_medicus_helpdesk_website_autofill.controllers.website_form import (
    WebsiteFormAutofill,
)

# Fields resolved by the server; a website visitor must never post them.
_TD_PROTECTED_KEYS = (
    'partner_id',
    'product_id',
    'lot_id',
    'td_applicant_id',
    'td_applicant_edrpou',
)


class WebsiteFormEquipment(WebsiteFormAutofill):

    def extract_data(self, model, values):
        return super().extract_data(model, self._td_sanitize_values(values))

    @staticmethod
    def _td_sanitize_values(values):
        """AC-20: drop the fields the website visitor must not set."""
        return {key: value for key, value in values.items()
                if key not in _TD_PROTECTED_KEYS}

    def _td_autofill_helpdesk(self, values, data):
        """AC-16: replaces the lookup of td_medicus_helpdesk_website_autofill,
        which searched the serial number among the client's deliveries only."""
        result = request.env['helpdesk.ticket'].sudo()._td_autofill_values(values)
        data.setdefault('record', {}).update(result['record'])
        if result['custom']:
            data['custom'] = '\n'.join(filter(None, [data.get('custom'), *result['custom']]))
