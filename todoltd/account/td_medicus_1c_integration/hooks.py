import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def post_init_hook_fix_balances(env):
    """
    Автоматично перераховує старі рахунки для виправлення та балансу.
    """
    _logger.info("Starting post_init_hook to fix invoice balances...")
    
    invoices = env['account.move'].search([
        ('date', '>=', '2026-02-01'),
        ('move_type', 'in', ('out_invoice', 'out_refund')),
        ('payment_state', '=', 'not_paid'),
        ('state', '!=', 'cancel')
    ])
    
    if not invoices:
        _logger.info("No invoices found for balancing.")
        return

    for inv in invoices.with_context(check_move_validity=False):
        try:
            old_amount = inv.amount_total
            inv._compute_amount()
            inv._compute_tax_totals()
            
            if old_amount != inv.amount_total:
                _logger.info("Adjusted balance for %s: %s -> %s", inv.name, old_amount, inv.amount_total)
        except Exception as e:
            _logger.error("Failed to fix balance for %s: %s", inv.name, str(e))
            
    _logger.info("Post_init_hook finished successfully.")