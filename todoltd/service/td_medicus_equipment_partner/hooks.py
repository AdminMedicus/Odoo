# -*- coding: utf-8 -*-


def post_init_hook(env):
    """Backfills for the data that exists before the module is installed."""
    Ticket = env['helpdesk.ticket']
    # AC-10: ticket equipment from the stock.lot.report fields.
    Ticket._td_migrate_equipment_fields()
    # AC-05: lot owners from the delivery history (open tickets follow them).
    env['stock.lot']._td_backfill_owners()
    # Closed tickets get the owner their serial number has at install time.
    Ticket.with_context(active_test=False).search([('lot_id', '!=', False)])._td_refresh_owner()
    # AC-37: applicants of the existing tickets.
    Ticket._td_backfill_applicants()
