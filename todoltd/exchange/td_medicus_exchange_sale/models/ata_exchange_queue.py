from contextlib import contextmanager
from contextvars import ContextVar

from odoo import api, models


# The base ata_exchange_v4 implementation stores this state in a Python class
# attribute.  That state is shared by concurrent work handled in the same
# process and can therefore suppress an unrelated user's queue event.  Keep
# the compatibility fix in this Medicus extension because ata_exchange_v4 is
# a protected module on this project.
_QUEUE_DISABLE_DEPTH = ContextVar(
    "td_medicus_exchange_queue_disable_depth",
    default=0,
)


class AtaExchangeQueue(models.Model):
    _inherit = "ata.exchange.queue"

    @contextmanager
    def disable_add_temporarily(self, disable=True):
        """Disable enqueueing only in the current execution context."""
        if not disable:
            yield
            return

        token = _QUEUE_DISABLE_DEPTH.set(_QUEUE_DISABLE_DEPTH.get() + 1)
        try:
            yield
        finally:
            _QUEUE_DISABLE_DEPTH.reset(token)

    @api.model
    def change_in_queue(self, record):
        """Apply the base queue algorithm without process-global state."""
        if _QUEUE_DISABLE_DEPTH.get():
            return False

        exchange_base = self.env["ata.exchange.base.outgoingdata"]
        if isinstance(record.id, api.NewId):
            return False

        methods = record.ata_exchange_compute_methods()
        if exchange_base._re_exchanged_in(record):
            return False

        queue = self.sudo()
        queue_usage = self.env["ata.exchange.queue.usage"].sudo()

        for method in methods:
            if queue_usage.use_exchange_queue(method):
                # Calling the inherited method on a sudo recordset also makes
                # its internal create() independent of the business user's
                # access rights and record rules.
                queue._add_to_queue(record, method)
            else:
                exchange_base.exchange_outgoing_data(record, method)

        if record.ref_cache_queue_possible():
            queue.search([
                ("ref_object", "=", record.ref_cache),
                ("method", "not in", [method.id for method in methods]),
            ]).unlink()

        return True
