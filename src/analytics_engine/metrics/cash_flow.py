"""Cash flow metrics — net operating cash flow, burn rate, runway."""

from __future__ import annotations

import duckdb

from analytics_engine.core.types import MetricResult
from analytics_engine.metrics.base import MetricContext, metric_registry


@metric_registry.register
class NetOperatingCashFlowMetric:
    code = "cash_flow.net_operating"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        result = duck.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN voucher_type = 'Receipt' THEN amount_paise ELSE 0 END), 0) AS inflows,
                COALESCE(SUM(CASE WHEN voucher_type = 'Payment' THEN amount_paise ELSE 0 END), 0) AS outflows,
                COALESCE(SUM(CASE WHEN voucher_type = 'Sales' THEN amount_paise ELSE 0 END), 0) AS sales,
                COALESCE(SUM(CASE WHEN voucher_type = 'Purchase' THEN amount_paise ELSE 0 END), 0) AS purchases
            FROM mart_vouchers
            WHERE TRY_CAST(date AS DATE) BETWEEN ? AND ?
        """, [str(ctx.period_start), str(ctx.period_end)]).fetchone()

        if not result:
            return []

        inflows, outflows, sales, purchases = result
        net_cf = inflows - outflows

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=float(net_cf),
            value_json={
                "inflows_paise": inflows,
                "outflows_paise": outflows,
                "sales_paise": sales,
                "purchases_paise": purchases,
                "net_cf_paise": net_cf,
            },
            unit="inr_paise",
            version=self.version,
        )]


@metric_registry.register
class BurnRateMetric:
    code = "cash_flow.burn_rate"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        # Monthly outflow rate
        result = duck.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN voucher_type = 'Payment' THEN amount_paise ELSE 0 END), 0) AS total_outflows,
                COUNT(DISTINCT STRFTIME(TRY_CAST(date AS DATE), '%Y-%m')) AS months_active
            FROM mart_vouchers
            WHERE voucher_type = 'Payment'
              AND TRY_CAST(date AS DATE) BETWEEN ? AND ?
        """, [str(ctx.period_start), str(ctx.period_end)]).fetchone()

        if not result or result[1] == 0:
            return []

        total_outflows, months = result
        monthly_burn = total_outflows / months

        # Cash on hand
        cash_row = duck.execute("""
            SELECT COALESCE(SUM(closing_balance_paise), 0)
            FROM mart_ledgers
            WHERE standard_category IN ('cash', 'bank')
        """).fetchone()
        cash_on_hand = cash_row[0] if cash_row else 0

        daily_burn = monthly_burn / 30 if monthly_burn > 0 else 0
        runway_days = cash_on_hand / daily_burn if daily_burn > 0 else None

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=runway_days,
            value_json={
                "monthly_burn_paise": int(monthly_burn),
                "cash_on_hand_paise": cash_on_hand,
                "runway_days": runway_days,
            },
            unit="days",
            version=self.version,
        )]
