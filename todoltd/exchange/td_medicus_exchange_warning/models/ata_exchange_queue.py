import json

from odoo import api, models


class AtaExchangeQueue(models.Model):
    _inherit = 'ata.exchange.queue'

    @api.model
    def retry_exchange(self, records):
        ExBase = self.env['ata.exchange.base.outgoingdata']
        for record in records:
            if isinstance(record.id, api.NewId):
                continue

            methods = record.ata_exchange_compute_methods()
            if ExBase._re_exchanged_in(record):
                continue

            for method in methods:
                if self.env['ata.exchange.queue.usage'].use_exchange_queue(method):
                    self._retry_record_method(record, method)
                else:
                    result_update = ExBase.exchange_outgoing_data(record, method)
                    if result_update.success and hasattr(record, 'ata_exchange_clear_error'):
                        record.ata_exchange_clear_error(method)
                    if result_update.error and hasattr(record, 'ata_exchange_set_error'):
                        record.ata_exchange_set_error(
                            self._format_error_message(result_update.error),
                            method)

    @api.model
    def _retry_record_method(self, record, method):
        ref_record = record.ref_cache
        if not ref_record:
            return

        if not self.env['ata.exchange.domain'].get_ext_systems(record, method):
            return
        if not record.ata_exchange_validate_main(method):
            return

        queue_record = self.sudo().search([
            ('ref_object', '=', ref_record),
            ('method', '=', method.id),
        ], limit=1)
        if queue_record:
            queue_record.write({
                'state_exchange': 'new',
                'error_last': False,
            })
        else:
            self._add_to_queue(record, method)

        if self.env['ata.exchange.queue.usage'].use_immediate_exchange(method):
            self.env.ref('ata_exchange_v4.ata_exchange_queue_cron')._trigger()

    @api.model
    def _format_error_message(self, error):
        if not error:
            return ''
        if isinstance(error, dict):
            message = error.get('message') or error.get('error') or ''
            data = error.get('data')
            if data:
                try:
                    data_message = json.dumps(data, ensure_ascii=False)
                except TypeError:
                    data_message = str(data)
                message = f'{message}. {data_message}' if message else data_message
            return message or str(error)
        return str(error)

    def write(self, vals):
        result = super().write(vals)
        for record in self:
            ref_object = record.get_ref_object_as_exclass()
            if not ref_object:
                continue

            if record.state_exchange == 'idle' and record.error_last and hasattr(ref_object, 'ata_exchange_set_error'):
                ref_object.ata_exchange_set_error(record.error_last, record.method)
            elif record.state_exchange == 'done' and hasattr(ref_object, 'ata_exchange_clear_error'):
                ref_object.ata_exchange_clear_error(record.method)

        return result

    def unlink(self):
        for record in self:
            ref_object = record.get_ref_object_as_exclass()
            if ref_object and hasattr(ref_object, 'ata_exchange_clear_error'):
                ref_object.ata_exchange_clear_error(record.method)

        return super().unlink()
