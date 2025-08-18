from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = "stock.picking"

    td_currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='purchase_id.currency_id'
    )

    td_currency_rate = fields.Float(
        string="Currency Rate",
        digits=(12, 6),
        compute='_compute_currency_id_set_rate',
        readonly=True
    )

    td_type_of_trade = fields.Selection(
        [
            ('prepayment', 'Prepayment'),
            ('credit', 'Credit'),
            ('res_storage', 'Responsible Storage'),
        ], default='prepayment',
        related='purchase_id.td_type_of_trade'
    )

    td_is_import = fields.Boolean(
        string="Import",
        default=False,
        related='purchase_id.td_is_import'
    )

    state = fields.Selection(
        selection_add=[('import', 'Import data to 1C')],
    )

    def td_button_send_data_to_one_c(self):
        pass

    @api.depends('td_currency_id')
    def _compute_currency_id_set_rate(self):
        for record in self:
            if not record.td_currency_id:
                record.td_currency_rate = 1.0
                continue

            company_currency = record.company_id.currency_id
            if record.td_currency_id == company_currency:
                record.td_currency_rate = 1.0
                continue

            # rate = self.env['res.currency.rate'].search(
            #     [('currency_id', '=', record.td_currency_id.id)],
            #     order='name desc',
            #     limit=1
            # )

            if record.td_currency_id:
                record.td_currency_rate = record.td_currency_id.rate
            else:
                record.td_currency_rate = 1.0

    def button_validate(self):
        if not self.td_is_import:
            res = super().button_validate()
            if self and self.id:
                for picking in self:
                    for move in picking.move_ids:
                        for lot in move.lot_ids:
                            uktzed_line = move.move_line_ids.filtered(lambda lin: lin.lot_id.id == lot.id)
                            move.lot_ids.write({
                                'td_uktzed_code_id': uktzed_line.td_uktzed_code_id.id if uktzed_line else False
                            })
                            move.td_uktzed_code_id = uktzed_line.td_uktzed_code_id.id if uktzed_line else False
            return res
        return False
