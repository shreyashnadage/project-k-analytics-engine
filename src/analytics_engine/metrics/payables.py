"""Payables metrics — DPO, aging buckets, creditor concentration."""

from __future__ import annotations

import duckdb

from analytics_engine.core.types import MetricResult
from analytics_engine.metrics.base import MetricContext, metric_registry


@metric_registry.register
class DPOMetric:
    code = "payables.dpo"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        result = duck.execute("""
            WITH purchases AS (
                SELECT COALESCE(SUM(amount_paise), 0) AS net_purchases
                FROM mart_vouchers
                WHERE voucher_type = 'Purchase'
                  AND TRY_CAST(date AS DATE) BETWEEN ? AND ?
            ),
            ap AS (
                SELECT COALESCE(SUM(ABS(closing_balance_paise)), 0) AS total_ap
                FROM mart_ledgers
                WHERE standard_category = 'sundry_creditors'
            )
            SELECT
                CASE WHEN p.net_purchases > 0
                     THEN (ap.total_ap * ? * 1.0) / p.net_purchases
                     ELSE NULL
                END AS dpo
            FROM purchases p, ap
        """, [str(ctx.period_start), str(ctx.period_end), ctx.days_in_period]).fetchone()

        dpo_value = result[0] if result else None

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=dpo_value,
            value_json=None,
            unit="days",
            version=self.version,
        )]


@metric_registry.register
class PayablesAgingMetric:
    code = "payables.aging_buckets"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        result = duck.execute("""
            WITH outstanding_purchases AS (
                SELECT
                    party,
                    amount_paise,
                    TRY_CAST(date AS DATE) AS purchase_date,
                    DATEDIFF('day', TRY_CAST(date AS DATE), ?) AS age_days
                FROM mart_vouchers
                WHERE voucher_type = 'Purchase'
                  AND TRY_CAST(date AS DATE) IS NOT NULL
            )
            SELECT
                COALESCE(SUM(CASE WHEN age_days <= 30 THEN amount_paise ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN age_days BETWEEN 31 AND 60 THEN amount_paise ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN age_days BETWEEN 61 AND 90 THEN amount_paise ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN age_days BETWEEN 91 AND 180 THEN amount_paise ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN age_days > 180 THEN amount_paise ELSE 0 END), 0),
                COALESCE(SUM(amount_paise), 0)
            FROM outstanding_purchases
        """, [str(ctx.period_end)]).fetchone()

        if not result:
            return []

        buckets = {
            "0-30": result[0], "31-60": result[1], "61-90": result[2],
            "91-180": result[3], "180+": result[4], "total": result[5],
        }

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=None,
            value_json=buckets,
            unit="inr_paise",
            version=self.version,
        )]


@metric_registry.register
class PayablesConcentrationMetric:
    code = "payables.concentration"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        total_row = duck.execute(
            "SELECT COALESCE(SUM(total_paise), 0) FROM mart_purchases_by_party"
        ).fetchone()
        total = total_row[0] if total_row else 0

        if total == 0:
            return [MetricResult(
                metric_code=self.code, period_start=ctx.period_start,
                period_end=ctx.period_end, value_numeric=0.0,
                value_json={"top_parties": [], "total_paise": 0}, unit="percent",
                version=self.version,
            )]

        top_parties = duck.execute("""
            SELECT party, total_paise, voucher_count
            FROM mart_purchases_by_party ORDER BY total_paise DESC LIMIT 10
        """).fetchall()

        parties_list = [
            {"party": p, "total_paise": amt, "percentage": round(amt * 100.0 / total, 2), "voucher_count": c}
            for p, amt, c in top_parties
        ]
        top_3_pct = sum(p["percentage"] for p in parties_list[:3])

        return [MetricResult(
            metric_code=self.code, period_start=ctx.period_start,
            period_end=ctx.period_end, value_numeric=top_3_pct,
            value_json={"top_parties": parties_list, "total_paise": total, "top_3_pct": top_3_pct},
            unit="percent", version=self.version,
        )]
