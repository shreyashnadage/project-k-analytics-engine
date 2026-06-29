"""Revenue metrics — monthly trend, month-over-month growth."""

from __future__ import annotations

import duckdb

from analytics_engine.core.types import MetricResult
from analytics_engine.metrics.base import MetricContext, metric_registry


@metric_registry.register
class MonthlyTrendMetric:
    code = "revenue.monthly_trend"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        rows = duck.execute("""
            SELECT month, total_paise, voucher_count
            FROM mart_monthly_summary
            WHERE voucher_type = 'Sales'
              AND month >= STRFTIME(CAST(? AS DATE), '%Y-%m')
              AND month <= STRFTIME(CAST(? AS DATE), '%Y-%m')
            ORDER BY month
        """, [str(ctx.period_start), str(ctx.period_end)]).fetchall()

        trend = [
            {"month": m, "total_paise": p, "voucher_count": c}
            for m, p, c in rows
        ]

        total_paise = sum(r["total_paise"] for r in trend)

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=float(total_paise),
            value_json={"months": trend, "total_paise": total_paise},
            unit="inr_paise",
            version=self.version,
        )]


@metric_registry.register
class MoMGrowthMetric:
    code = "revenue.mom_growth"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        rows = duck.execute("""
            SELECT month, total_paise
            FROM mart_monthly_summary
            WHERE voucher_type = 'Sales'
            ORDER BY month
        """).fetchall()

        if len(rows) < 2:
            return [MetricResult(
                metric_code=self.code, period_start=ctx.period_start,
                period_end=ctx.period_end, value_numeric=None,
                value_json={"growth_series": []}, unit="percent",
                version=self.version,
            )]

        growth_series = []
        for i in range(1, len(rows)):
            prev_month, prev_amount = rows[i - 1]
            curr_month, curr_amount = rows[i]
            if prev_amount > 0:
                growth_pct = round((curr_amount - prev_amount) * 100.0 / prev_amount, 2)
            else:
                growth_pct = None
            growth_series.append({
                "month": curr_month,
                "growth_pct": growth_pct,
                "current_paise": curr_amount,
                "previous_paise": prev_amount,
            })

        latest_growth = growth_series[-1]["growth_pct"] if growth_series else None

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=latest_growth,
            value_json={"growth_series": growth_series},
            unit="percent",
            version=self.version,
        )]
