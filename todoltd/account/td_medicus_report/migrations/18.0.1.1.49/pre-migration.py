# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("td_medicus_report: starting pre-migration for td_ttn_gross_weight")

    cr.execute("""
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = 'stock_picking'
           AND column_name = 'td_ttn_gross_weight'
         LIMIT 1
    """)
    row = cr.fetchone()

    if not row:
        _logger.info("td_medicus_report: column stock_picking.td_ttn_gross_weight not found, skipping")
        return

    data_type = row[0]
    _logger.info("td_medicus_report: current type of td_ttn_gross_weight = %s", data_type)

    if data_type in ('double precision', 'numeric', 'real'):
        _logger.info("td_medicus_report: td_ttn_gross_weight is already numeric, skipping")
        return

    if data_type not in ('character varying', 'character', 'text'):
        _logger.warning(
            "td_medicus_report: unexpected type for td_ttn_gross_weight: %s. Migration skipped.",
            data_type,
        )
        return

    cr.execute("""
        ALTER TABLE stock_picking
        ALTER COLUMN td_ttn_gross_weight TYPE double precision
        USING CASE
            WHEN td_ttn_gross_weight IS NULL THEN NULL
            WHEN btrim(td_ttn_gross_weight) = '' THEN NULL
            WHEN regexp_replace(replace(btrim(td_ttn_gross_weight), ',', '.'), '\s+', '', 'g')
                 ~ '^[+-]?([0-9]+([.][0-9]+)?|[.][0-9]+)$'
            THEN regexp_replace(replace(btrim(td_ttn_gross_weight), ',', '.'), '\s+', '', 'g')::double precision
            ELSE NULL
        END
    """)

    _logger.info("td_medicus_report: td_ttn_gross_weight successfully converted to double precision")
