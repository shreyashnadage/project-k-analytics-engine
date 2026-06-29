"""Cash Conversion Cycle metric — DSO + DIO - DPO."""

from __future__ import annotations

import duckdb

from analytics_engine.core.types import MetricResult
from analytics_engine.metrics.base import MetricContext, metric_registry


@metric_registry.register
class CashConversionCycleMetric:
    code = "ccc.cash_conversion_cycle"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        days = ctx.days_in_period
        period_start = str(ctx.period_start)
        period_end = str(ctx.period_end)

        row = duck.execute("""
            WITH financials AS (
                SELECT
                    COALESCE(SUM(CASE WHEN voucher_type = 'Sales' THEN amount_paise ELSE 0 END), 0) AS sales,
                    COALESCE(SUM(CASE WHEN voucher_type = 'Purchase' THEN amount_paise ELSE 0 END), 0) AS cogs
                FROM mart_vouchers
                WHERE TRY_CAST(date AS DATE) BETWEEN ? AND ?
            ),
            balances AS (
                SELECT
                    COALESCE(SUM(CASE WHEN standard_category = 'sundry_debtors'
                        THEN closing_balance_paise ELSE 0 END), 0) AS ar,
                    COALESCE(SUM(CASE WHEN standard_category = 'sundry_creditors'
                        THEN ABS(closing_balance_paise) ELSE 0 END), 0) AS ap
                FROM mart_ledgers
            )
            SELECT
                f.sales, f.cogs, b.ar, b.ap
            FROM financials f, balances b
        """, [period_start, period_end]).fetchone()

        if not row:
            return []

        sales, cogs, ar, ap = row

        dso = (ar * days / sales) if sales > 0 else None
        dpo = (ap * days / cogs) if cogs > 0 else None

        # DIO: would need inventory data — use 0 for MVP if no stock ledgers
        inventory_row = duck.execute("""
            SELECT COALESCE(SUM(closing_balance_paise), 0)
            FROM mart_ledgers
            WHERE standard_category = 'current_asset'
              AND (name ILIKE '%stock%' OR name ILIKE '%inventory%')
        """).fetchone()
        inventory = inventory_row[0] if inventory_row else 0
        dio = (inventory * days / cogs) if cogs > 0 else 0

        ccc = None
        if dso is not None and dpo is not None:
            ccc = dso + dio - dpo

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=round(ccc, 2) if ccc is not None else None,
            value_json={
                "dso": round(dso, 2) if dso else None,
                "dio": round(dio, 2) if dio else None,
                "dpo": round(dpo, 2) if dpo else None,
                "ccc": round(ccc, 2) if ccc else None,
            },
            unit="days",
            version=self.version,
        )]
