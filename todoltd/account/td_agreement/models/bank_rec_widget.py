from logging import getLogger
from odoo import api, models, fields, Command

_logger = getLogger(__name__)


class BankRecWidgetLine(models.Model):
    _inherit = "bank.rec.widget.line"

    td_agreement_id = fields.Many2one(
        string="Agreement",
        comodel_name="td.agreement",
        ondelete="restrict",
        compute="_compute_td_agreement_id",
    )

    @api.depends("source_aml_move_id.td_agreement_id")
    def _compute_td_agreement_id(self):
        for rec in self:
            rec.td_agreement_id = rec.source_aml_move_id.td_agreement_id

    def _get_aml_values(self, **kwargs):
        # EXTENDS account_accountant
        return super()._get_aml_values(
            **kwargs,
            td_agreement_id=self.td_agreement_id.id,
        )


class BankRecWidget(models.Model):
    _inherit = "bank.rec.widget"

    def _line_value_changed_td_agreement_id(self, line):
        self.ensure_one()
        self._lines_turn_auto_balance_into_manual_line(line)

    def _action_validate(self):
        self.ensure_one()
        partners = (self.line_ids.filtered(lambda x: x.flag != "liquidity")).partner_id
        partner_to_set = partners if len(partners) == 1 else self.env["res.partner"]

        # Prepare the lines to be created.
        to_reconcile = []
        line_ids_create_command_list = []
        aml_to_exchange_diff_vals = {}

        source2exchange = self.line_ids.filtered(
            lambda l: l.flag == "exchange_diff"
        ).grouped("source_aml_id")
        for i, line in enumerate(self.line_ids):
            if line.flag == "exchange_diff":
                continue

            amount_currency = line.amount_currency
            balance = line.balance
            if line.flag == "new_aml":
                to_reconcile.append((i, line.source_aml_id))
                exchange_diff = source2exchange.get(line.source_aml_id)
                if exchange_diff:
                    aml_to_exchange_diff_vals[i] = {
                        "amount_residual": exchange_diff.balance,
                        "amount_residual_currency": exchange_diff.amount_currency,
                        "analytic_distribution": exchange_diff.analytic_distribution,
                    }
                    # Squash amounts of exchange diff into corresponding new_aml
                    amount_currency += exchange_diff.amount_currency
                    balance += exchange_diff.balance
            line_ids_create_command_list.append(
                Command.create(
                    line._get_aml_values(
                        sequence=i,
                        partner_id=partner_to_set.id
                        if line.flag in ("liquidity", "auto_balance")
                        else line.partner_id.id,
                        amount_currency=amount_currency,
                        balance=balance,
                    )
                )
            )

        st_line = self.st_line_id
        move = st_line.move_id

        # Update the move.
        move_ctx = move.with_context(
            force_delete=True,
            skip_readonly_check=True,
        )
        move_ctx.write(
            {
                "partner_id": partner_to_set.id,
                "line_ids": [Command.clear()] + line_ids_create_command_list,
            }
        )
        if move_ctx.state == "draft":
            move_ctx.action_post()

        AccountMoveLine = self.env["account.move.line"]
        sequence2lines = move_ctx.line_ids.grouped("sequence")
        lines = [
            (sequence2lines[index], counterpart_aml)
            for index, counterpart_aml in to_reconcile
        ]
        all_line_ids = tuple(
            {_id for line, counterpart in lines for _id in (line + counterpart).ids}
        )
        # Handle exchange diffs
        exchange_diff_moves = None
        lines_with_exch_diff = AccountMoveLine
        if aml_to_exchange_diff_vals:
            exchange_diff_vals_list = []
            for line, counterpart in lines:
                line = line.with_prefetch(all_line_ids)
                counterpart = counterpart.with_prefetch(all_line_ids)
                exchange_diff_amounts = aml_to_exchange_diff_vals.get(line.sequence, {})
                exchange_analytic_distribution = exchange_diff_amounts.pop(
                    "analytic_distribution", False
                )
                if exchange_diff_amounts:
                    related_exchange_diff_amls = (
                        line
                        if exchange_diff_amounts["amount_residual"]
                        * line.amount_residual
                        > 0
                        else counterpart
                    )
                    exchange_diff_vals_list.append(
                        related_exchange_diff_amls._prepare_exchange_difference_move_vals(
                            [exchange_diff_amounts],
                            exchange_date=max(line.date, counterpart.date),
                            exchange_analytic_distribution=exchange_analytic_distribution,
                        )
                    )
                    lines_with_exch_diff += line
            exchange_diff_moves = AccountMoveLine._create_exchange_difference_moves(
                exchange_diff_vals_list
            )

        # Perform the reconciliation.
        self.env["account.move.line"].with_context(
            no_exchange_difference=True
        )._reconcile_plan(
            [
                (line + counterpart).with_prefetch(all_line_ids)
                for line, counterpart in lines
            ]
        )

        # Assign exchange move to partials.
        for index, line in enumerate(lines_with_exch_diff):
            exchange_move = exchange_diff_moves[index]
            for debit_credit in ("debit", "credit"):
                partials = line[f"matched_{debit_credit}_ids"].filtered(
                    lambda partial: partial[f"{debit_credit}_move_id"].move_id
                    != exchange_move
                )
                partials.exchange_move_id = exchange_move

        # Fill missing partner.
        st_line_ctx = st_line.with_context(skip_account_move_synchronization=True)
        st_line_ctx.partner_id = partner_to_set

        # Create missing partner bank if necessary.
        if (
            st_line.account_number
            and st_line.partner_id
            and not st_line.partner_bank_id
        ):
            st_line_ctx.partner_bank_id = st_line._find_or_create_bank_account()

        # Refresh analytic lines.
        move.line_ids.analytic_line_ids.unlink()
        move.line_ids.with_context(validate_analytic=True)._create_analytic_lines()
        lines = move.line_ids._all_reconciled_lines()
        _logger.info("THIS IS LINES %s", move)
        for line in lines:
            if line.move_id.td_agreement_id:
                _logger.info(line.move_id.td_agreement_id)
                move.td_agreement_id = line.move_id.td_agreement_id.id
                break
