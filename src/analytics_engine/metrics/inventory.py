"""Inventory metrics — DIO, stock turnover (for trading/manufacturing verticals)."""

from __future__ import annotations

import duckdb

from analytics_engine.core.types import MetricResult
from analytics_engine.metrics.base import MetricContext, metric_registry


@metric_registry.register
class DIOMetric:
    code = "inventory.dio"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        row = duck.execute("""
            WITH cogs AS (
                SELECT COALESCE(SUM(amount_paise), 0) AS total_cogs
                FROM mart_vouchers
                WHERE voucher_type = 'Purchase'
                  AND TRY_CAST(date AS DATE) BETWEEN ? AND ?
            ),
            inv AS (
                SELECT COALESCE(SUM(closing_balance_paise), 0) AS avg_inventory
                FROM mart_ledgers
                WHERE standard_category = 'current_asset'
                  AND (name ILIKE '%stock%' OR name ILIKE '%inventory%')
            )
            SELECT
                CASE WHEN c.total_cogs > 0
                     THEN (inv.avg_inventory * ? * 1.0) / c.total_cogs
                     ELSE NULL
                END AS dio
            FROM cogs c, inv
        """, [str(ctx.period_start), str(ctx.period_end), ctx.days_in_period]).fetchone()

        dio = row[0] if row else None

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=round(dio, 2) if dio is not None else None,
            value_json=None,
            unit="days",
            version=self.version,
        )]


@metric_registry.register
class StockTurnoverMetric:
    code = "inventory.stock_turnover"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        row = duck.execute("""
            WITH cogs AS (
                SELECT COALESCE(SUM(amount_paise), 0) AS total_cogs
                FROM mart_vouchers
                WHERE voucher_type = 'Purchase'
                  AND TRY_CAST(date AS DATE) BETWEEN ? AND ?
            ),
            inv AS (
                SELECT COALESCE(SUM(closing_balance_paise), 0) AS avg_inventory
                FROM mart_ledgers
                WHERE standard_category = 'current_asset'
                  AND (name ILIKE '%stock%' OR name ILIKE '%inventory%')
            )
            SELECT
                CASE WHEN inv.avg_inventory > 0
                     THEN c.total_cogs * 1.0 / inv.avg_inventory
                     ELSE NULL
                END AS turnover
            FROM cogs c, inv
        """, [str(ctx.period_start), str(ctx.period_end)]).fetchone()

        turnover = row[0] if row else None

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=round(turnover, 4) if turnover is not None else None,
            value_json=None,
            unit="ratio",
            version=self.version,
        )]
