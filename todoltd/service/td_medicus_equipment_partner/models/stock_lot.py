# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.osv import expression

# Groups allowed to change the owner of a serial number by hand.
OWNER_MANAGER_GROUPS = ('helpdesk.group_helpdesk_manager', 'stock.group_stock_manager')


class StockLot(models.Model):
    _inherit = 'stock.lot'

    td_owner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Owner',
        tracking=True,
        index=True,
        help='Company that bought this unit: set by sale deliveries, cleared by '
             'their returns, editable by helpdesk and inventory managers.',
    )
    td_applicant_ids = fields.One2many(
        comodel_name='td.equipment.applicant',
        inverse_name='lot_id',
        string='Applicants',
    )
    td_serviced_for_client = fields.Boolean(
        string='Serviced for This Client',
        compute='_compute_td_serviced_for_client',
        search='_search_td_serviced_for_client',
    )

    def write(self, vals):
        """AC-06: only helpdesk and inventory managers change the owner by hand.
        Deliveries and returns update it with ``sudo()``."""
        if 'td_owner_id' in vals and not self.env.su and not any(
                self.env.user.has_group(group) for group in OWNER_MANAGER_GROUPS):
            raise AccessError(_(
                'Only helpdesk or inventory managers can change the owner of a '
                'serial number.'))
        result = super().write(vals)
        if 'td_owner_id' in vals:
            # AC-12: open tickets follow the new owner, closed ones keep theirs.
            self.env['helpdesk.ticket'].sudo().search([
                ('lot_id', 'in', self.ids),
                ('stage_id.fold', '=', False),
            ])._td_refresh_owner()
        return result

    def _td_client_from_context(self):
        client_id = self.env.context.get('td_client_id')
        return self.env['res.partner'].browse(client_id).commercial_partner_id

    @api.model
    def _td_serviced_domain(self, client):
        """Lots the client owns or applied for (by partner or by its EDRPOU)."""
        if not client:
            return expression.FALSE_DOMAIN
        applicant = [('partner_id', '=', client.id)]
        if client.company_registry:
            applicant = expression.OR([applicant, [('edrpou', '=', client.company_registry)]])
        return expression.OR([
            [('td_owner_id', '=', client.id)],
            [('td_applicant_ids', 'any', applicant)],
        ])

    @api.depends_context('td_client_id')
    def _compute_td_serviced_for_client(self):
        """AC-36"""
        domain = self._td_serviced_domain(self._td_client_from_context())
        serviced = self.search(expression.AND([[('id', 'in', self.ids)], domain]))
        for lot in self:
            lot.td_serviced_for_client = lot in serviced

    def _search_td_serviced_for_client(self, operator, value):
        """AC-36: the "Serviced for This Client" filter of the serial number
        search; the ticket passes its client in the context key ``td_client_id``."""
        if operator not in ('=', '!='):
            raise NotImplementedError(_('Operation not supported'))
        domain = self._td_serviced_domain(self._td_client_from_context())
        return domain if (operator == '=') == bool(value) else ['!'] + domain

    @api.model
    def _td_backfill_owners(self):
        """AC-05: Replay the sale deliveries and their returns done before install,
        oldest first, so every lot ends with the owner the live rules would give."""
        pickings = self.env['stock.picking'].sudo().search([
            ('state', '=', 'done'),
            ('move_line_ids.lot_id', '!=', False),
            '|', ('picking_type_code', '=', 'outgoing'), ('return_id', '!=', False),
        ]).sorted(lambda picking: (picking.date_done, picking.id))
        for picking in pickings:
            picking._td_update_lot_owners()
