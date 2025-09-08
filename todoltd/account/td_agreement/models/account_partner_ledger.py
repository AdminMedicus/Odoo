from odoo import api, models, _
from odoo.tools import SQL
from odoo.tools.float_utils import float_is_zero
from odoo.osv import expression


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def open_journal_items(self, options, params):
        action = super().open_journal_items(options, params)

        if self._groupby_agreement_enabled(options):
            report = self._get_report(options, default_ref='account_reports.partner_ledger_report')
            record_model, record_id, record, partner = self._get_line_info_with_partner(report, params['line_id'])

            if record_model == 'res.partner':
                action['context']['search_default_group_by_agreement_id'] = 1

            elif record_model == 'td.agreement':
                action['domain'] = expression.AND([
                    action['domain'],
                    [
                        ('partner_id', '=', partner.id),
                        ('td_agreement_id', '=', record_id),
                    ],
                ])

                action['context']['search_default_group_by_partner'] = 0

        return action

    def _get_custom_display_config(self):
        config = super()._get_custom_display_config() or {}

        templates = config.get('templates') or {}
        templates['AccountReportFilters'] = 'td_agreement.PartnerLedgerFilters'
        config['templates'] = templates

        return config

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options['td_custom_groupby'] = (previous_options or {}).get('td_custom_groupby', False)

    def _report_expand_unfoldable_line_partner_ledger(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        groupby_agreement = self._groupby_agreement_enabled(options)

        if groupby_agreement and not self._context.get('print_mode'):
            self = self.with_context(print_mode=True)

        result = super()._report_expand_unfoldable_line_partner_ledger(
            line_dict_id,
            groupby,
            options,
            progress,
            offset,
            unfold_all_batch_data=unfold_all_batch_data,
        )

        if groupby_agreement:
            report = self._get_report(options, 'account_reports.partner_ledger_report')
            force_expand_agreement_ids = self._context.get('force_expand_agreement_ids')

            lines_initial, lines, lines_total = self._split_lines_by_markup(report, result['lines'])

            agreements = self._create_agreement_info(report, options, line_dict_id, lines)

            new_lines = []
            for agreement_info in agreements:
                agreement_line_id = agreement_info.get('agreement_line_id')

                columns_metadata = agreement_info['columns_metadata']
                columns_initial = agreement_info['columns_initial']
                columns_values = agreement_info['columns_values']
                for i, column in columns_metadata.items():
                    columns_values[i]['name'] = report.format_value(
                        options,
                        columns_values[i]['no_format'],
                        figure_type=column['figure_type'],
                    )
                    columns_initial[i]['name'] = report.format_value(
                        options,
                        columns_initial[i]['no_format'],
                        figure_type=column['figure_type'],
                    )

                unfolded = agreement_line_id in options['unfolded_lines']

                new_lines.append({
                    'id': agreement_line_id,
                    'parent_id': line_dict_id,
                    'name': agreement_info['name'],
                    'class': 'text',
                    'columns': columns_values,
                    'level': 3,
                    'unfoldable': True,
                    'unfolded': unfolded or options['unfold_all'],
                    'expand_function': '_report_expand_unfoldable_line_contract',
                })

                if force_expand_agreement_ids and agreement_info['id'] in force_expand_agreement_ids:
                    if any([
                        not float_is_zero((r or {}).get('no_format') or 0.0, precision_rounding=self.env.company.currency_id.rounding)
                        for r in columns_initial
                    ]):
                        new_lines.append({
                            'id': report._get_generic_line_id(
                                None,
                                None,
                                parent_line_id=agreement_line_id,
                                markup='initial',
                            ),
                            'parent_id': agreement_line_id,
                            'class': 'o_account_reports_initial_balance',
                            'name': _("Initial Balance"),
                            'name_class': 'o_selferp_contract_settlement_initial_line_name',
                            'columns': columns_initial,
                            'level': 3,
                            'unfoldable': False,
                        })

                    new_lines += agreement_info['lines']

            result['lines'] = (
                lines_initial +
                new_lines +
                lines_total
            )

        return result

    def _report_expand_unfoldable_line_contract(self, line_dict_id, groupby, options, progress, offset, unfold_all_batch_data=None):
        result = {
            'lines': [],
            'has_more': False,
        }

        groupby_agreement = self._groupby_agreement_enabled(options)
        unfolded = line_dict_id or options['unfold_all']

        if groupby_agreement and unfolded:
            parent_line_id = line_dict_id[:line_dict_id.rindex('|')]
            dummy, record_id = self.env['account.report']._get_model_info_from_id(line_dict_id)

            expanded_partner = self.with_context(force_expand_agreement_ids=[record_id])._report_expand_unfoldable_line_partner_ledger(
                parent_line_id,
                groupby,
                options,
                progress,
                0,
                unfold_all_batch_data=None,
            )

            lines = list(filter(lambda r: r['parent_id'] == line_dict_id, expanded_partner['lines']))

            result['lines'] = lines

        return result

    def _create_agreement_info(self, report, options, parent_line_id, lines):
        TdAgreement = self.env['td.agreement']
        AccountMoveLine = self.env['account.move.line']

        move_lines_by_id = {}
        for line in lines:
            record_model, record_id = report._get_model_info_from_id(line.get('id'))
            if record_model == AccountMoveLine._name:
                move_lines_by_id[record_id] = line

        move_lines_additional_info = {}
        if move_lines_by_id:
            move_lines_domain = [('id', 'in', list(move_lines_by_id.keys()))]
            force_expand_agreement_ids = self._context.get('force_expand_agreement_ids')
            if force_expand_agreement_ids is not None:
                move_lines_domain += [('td_agreement_id', 'in', force_expand_agreement_ids)]

            move_lines_additional_info = {
                move_lines_by_id.get(r['id'])['id']: r
                for r in AccountMoveLine.search_read(
                    domain=move_lines_domain,
                    fields=['td_agreement_id'],
                )
                if r['id'] in move_lines_by_id
            }

        lines_by_agreement = {}
        for line in lines:
            agreement_id = None

            line_id = line.get('id')
            record_model, record_id = report._get_model_info_from_id(line_id)
            if record_model == AccountMoveLine._name:
                move_line_additional_info = move_lines_additional_info.get(line_id)
                if not move_line_additional_info:
                    continue
                agreement_id = move_line_additional_info['td_agreement_id'] and move_line_additional_info['td_agreement_id'][0] or None

            if agreement_id in lines_by_agreement:
                lines_by_agreement[agreement_id].append(line)
            else:
                lines_by_agreement[agreement_id] = [line]

        dummy, partner_id = report._get_model_info_from_id(parent_line_id)
        agreements = self._get_agreement_with_initial_balances(
            report,
            partner_id,
            list(lines_by_agreement.keys()),
            options,
        )

        for agreement_info in agreements:
            agreement_id = agreement_info['id']
            agreement_line_id = report._get_generic_line_id(
                TdAgreement._name,
                agreement_id,
                parent_line_id=parent_line_id,
            )
            agreement_info['agreement_line_id'] = agreement_line_id

            agreement_lines = lines_by_agreement.get(agreement_id)
            if agreement_lines:
                for line in agreement_lines:
                    record_model_name, record_id = report._get_model_info_from_id(line.get('id'))
                    line.update({
                        'id': report._get_generic_line_id(
                            record_model_name,
                            record_id,
                            parent_line_id=agreement_line_id,
                        ),
                        'parent_id': agreement_line_id,
                        'level': 4,
                    })

                    columns_metadata = agreement_info['columns_metadata']
                    columns_values = agreement_info['columns_values']
                    debit = 0.0
                    credit = 0.0
                    for i, column in columns_metadata.items():
                        line_columns = line['columns'][i] or {}
                        line['columns'][i] = line_columns
                        line_value = line_columns.get('no_format') or 0.0
                        expression_label = column.get('expression_label')

                        if expression_label == 'debit':
                            debit = line_value
                        elif expression_label == 'credit':
                            credit = line_value

                        if expression_label == 'balance':
                            line_balance = (columns_values[i].get('no_format') or 0.0) + debit - credit
                            line_columns['no_format'] = line_balance
                            line_columns['name'] = report.format_value(
                                options,
                                line_columns['no_format'],
                                figure_type=column['figure_type'],
                            )
                            columns_values[i]['no_format'] = line_balance
                        else:
                            columns_values[i]['no_format'] += line_value

                    agreement_info['lines'].append(line)

        agreements = sorted(agreements, key=lambda r: (r['id'] and 1 or 1000, r['name']))

        return agreements

    def _get_agreement_with_initial_balances(self, report, partner_id, agreement_ids, options):
        initial_balances = self._get_agreement_initial_balances(partner_id, options)

        agreement_ids = list(set((agreement_ids or []) + list(initial_balances.keys())))
        agreements_info = {
            r['id']: r['display_name']
            for r in self.env['td.agreement'].search_read(
                domain=[('id', 'in', agreement_ids)],
                fields=['name', 'display_name'],
            )
        }

        options_per_column_group = report._split_options_per_column_group(options)

        agreements = []

        for agreement_id in agreement_ids:
            balances = initial_balances.get(agreement_id) or {}
            columns_metadata = {}
            columns_initial = []
            columns_values = []

            column_index = 0
            for column_group_key, column_group_options in options_per_column_group.items():
                column_group_value = balances.get(column_group_key) or {}

                for column in column_group_options['columns']:
                    expression_label = column.get('expression_label')
                    if expression_label in ('debit', 'credit', 'balance'):
                        columns_metadata[column_index] = column

                        initial_value = column_group_value.get(expression_label) or 0.0
                        columns_initial.append({
                            'name': '',
                            'no_format': initial_value,
                            'class': 'numeric text-end',
                        })
                        columns_values.append({
                            'name': '',
                            'no_format': initial_value,
                            'class': 'numeric text-end',
                        })
                    else:
                        columns_initial.append({})
                        columns_values.append({})

                    column_index += 1

            agreements.append({
                'id': agreement_id,
                'name': agreement_id and agreements_info[agreement_id] or _("Undefined"),
                'lines': [],
                'columns_metadata': columns_metadata,
                'columns_initial': columns_initial,
                'columns_values': columns_values,
                'initial_debit': balances.get('debit') or 0.0,
                'initial_credit': balances.get('credit') or 0.0,
                'initial_balance': balances.get('balance') or 0.0,
            })

        return agreements

    def _get_agreement_initial_balances(self, partner_id, options):
        queries = []
        report = self.env.ref('account_reports.partner_ledger_report')
        for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
            # Get sums for the initial balance.
            # period: [('date' <= options['date_from'] - 1)]
            new_options = self._get_options_initial_balance(column_group_options)
            query = report._get_report_query(new_options, 'from_beginning', domain=[('partner_id', '=', partner_id)])
            queries.append(SQL(
                """
                SELECT
                    account_move_line.td_agreement_id,
                    %(column_group_key)s          AS column_group_key,
                    SUM(%(debit_select)s)         AS debit,
                    SUM(%(credit_select)s)        AS credit,
                    SUM(%(balance_select)s)       AS amount,
                    SUM(%(balance_select)s)       AS balance
                FROM %(table_references)s
                %(currency_table_join)s
                WHERE %(search_condition)s
                GROUP BY account_move_line.td_agreement_id
                """,
                column_group_key=column_group_key,
                debit_select=report._currency_table_apply_rate(SQL("account_move_line.debit")),
                credit_select=report._currency_table_apply_rate(SQL("account_move_line.credit")),
                balance_select=report._currency_table_apply_rate(SQL("account_move_line.balance")),
                table_references=query.from_clause,
                currency_table_join=report._currency_table_aml_join(column_group_options),
                search_condition=query.where_clause,
            ))

        self._cr.execute(SQL(" UNION ALL ").join(queries))

        result = {
            r['td_agreement_id']: {
                r['column_group_key']: r,
            }
            for r in self._cr.dictfetchall()
        }

        return result


        # ~~~~~~~~~~~~~V17~~~~~~~~~~~~~~~~
        # queries = []
        # params = []
        #
        # ct_query = report._get_query_currency_table(options)
        # options_per_column_group = report._split_options_per_column_group(options)
        #
        # for column_group_key, column_group_options in options_per_column_group.items():
        #     new_options = self._get_options_initial_balance(column_group_options)
        #     tables, where_clause, where_params = report._query_get(
        #         new_options,
        #         'normal',
        #         domain=[('partner_id', '=', partner_id)],
        #     )
        #
        #     params.append(column_group_key)
        #     params += where_params
        #
        #     queries.append(f'''
        #         SELECT account_move_line.td_agreement_id,
        #                %s                                                                                    as column_group_key,
        #                sum(round(account_move_line.debit * currency_table.rate, currency_table.precision))   as debit,
        #                sum(round(account_move_line.credit * currency_table.rate, currency_table.precision))  as credit,
        #                sum(round(account_move_line.balance * currency_table.rate, currency_table.precision)) as balance
        #           FROM {tables}
        #           LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
        #          WHERE {where_clause}
        #          GROUP BY account_move_line.td_agreement_id
        #     ''')
        #
        # self._cr.execute(' UNION ALL '.join(queries), params)
        # result = {
        #     r['td_agreement_id']: {
        #         r['column_group_key']: r,
        #     }
        #     for r in self._cr.dictfetchall()
        # }
        #
        # return result

    def _groupby_agreement_enabled(self, options):
        return (
            (options or {}).get('td_custom_groupby', False) == 'agreement'
        )

    def _split_lines_by_markup(self, report, lines_all):
        lines_initial = []
        lines = []
        lines_total = []

        for line in lines_all:
            markup, record_model, record_id = report._parse_line_id(line.get('id'))[-1]
            if markup == 'initial':
                lines_initial.append(line)
            elif markup == 'total':
                lines_total.append(line)
            else:
                lines.append(line)

        return lines_initial, lines, lines_total

    @api.model
    def _get_report(self, options, default_ref=None):
        report = None

        if options.get('report_id'):
            report = self.env['account.report'].browse(options.get('report_id')).exists()

        if not report and default_ref:
            report = self.env.ref(default_ref, raise_if_not_found=False)

        return report

    def _get_line_info_with_partner(self, report, line_id):
        ResPartner = self.env['res.partner']

        record_model, record_id = report._get_model_info_from_id(line_id)

        if record_model == 'res.partner':
            partner = ResPartner.browse(record_id).exists()
            return record_model, record_id, partner, partner

        else:
            record = self.env[record_model].browse(record_id).exists()

            partner_line_id = line_id.rsplit('|', 1)[0]
            dummy, partner_id = report._get_model_info_from_id(partner_line_id)
            partner = ResPartner.browse(partner_id).exists()

        return (
            record_model,
            record_id,
            record,
            partner,
        )
