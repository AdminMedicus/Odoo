# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.osv import expression


class TdAgreement(models.Model):
    _inherit = 'td.agreement'

    @api.model
    def _td_selection_domain(self, lot, partner):
        """AC-24: agreements of the serial number and agreements of the client."""
        domains = []
        if lot:
            domains.append([('td_lot_ids', 'in', lot.ids)])
        client = partner.commercial_partner_id
        if client:
            domains.append([('partner_id', 'child_of', client.id)])
        return expression.OR(domains) if domains else []

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """AC-25: with ``td_agreement_client_id`` in the context, list the client's
        agreements of the serial number (``td_agreement_lot_id``) first, then the
        client's other agreements, then those of the other counterparties."""
        client_id = self.env.context.get('td_agreement_client_id')
        if not client_id:
            return super().name_search(name, args, operator, limit)
        client = self.env['res.partner'].browse(client_id).commercial_partner_id
        lot_id = self.env.context.get('td_agreement_lot_id')
        own = [('partner_id', 'child_of', client.id)]
        on_lot = [('td_lot_ids', 'in', [lot_id])] if lot_id else expression.FALSE_DOMAIN
        groups = [
            expression.AND([own, on_lot]),
            expression.AND([own, ['!'] + on_lot]),
            ['!'] + own,
        ]
        results = []
        for group in groups:
            remaining = limit - len(results) if limit else None
            if remaining is not None and remaining <= 0:
                break
            results += super().name_search(
                name, expression.AND([args or [], group]), operator, remaining)
        return results

    @api.depends_context('td_agreement_client_id')
    def _compute_display_name(self):
        """AC-25: in the ticket and the service report every agreement names its
        counterparty, so a purchase agreement of A is not taken for a service
        agreement of B."""
        super()._compute_display_name()
        if self.env.context.get('td_agreement_client_id'):
            for agreement in self.filtered('partner_id'):
                agreement.display_name = '%s — %s' % (
                    agreement.display_name, agreement.partner_id.display_name)
