"""Receivables metrics — DSO, aging buckets, debtor concentration."""

from __future__ import annotations

import duckdb

from analytics_engine.core.types import MetricResult
from analytics_engine.metrics.base import MetricContext, metric_registry


@metric_registry.register
class DSOMetric:
    code = "receivables.dso"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        result = duck.execute("""
            WITH sales AS (
                SELECT COALESCE(SUM(amount_paise), 0) AS net_sales
                FROM mart_vouchers
                WHERE voucher_type = 'Sales'
                  AND TRY_CAST(date AS DATE) BETWEEN ? AND ?
            ),
            ar AS (
                SELECT COALESCE(SUM(closing_balance_paise), 0) AS total_ar
                FROM mart_ledgers
                WHERE standard_category = 'sundry_debtors'
            )
            SELECT
                CASE WHEN s.net_sales > 0
                     THEN (ar.total_ar * ? * 1.0) / s.net_sales
                     ELSE NULL
                END AS dso
            FROM sales s, ar
        """, [str(ctx.period_start), str(ctx.period_end), ctx.days_in_period]).fetchone()

        dso_value = result[0] if result else None

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=dso_value,
            value_json=None,
            unit="days",
            version=self.version,
        )]


@metric_registry.register
class ReceivablesAgingMetric:
    code = "receivables.aging_buckets"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        result = duck.execute("""
            WITH outstanding_sales AS (
                SELECT
                    party,
                    amount_paise,
                    TRY_CAST(date AS DATE) AS sale_date,
                    DATEDIFF('day', TRY_CAST(date AS DATE), ?) AS age_days
                FROM mart_vouchers
                WHERE voucher_type = 'Sales'
                  AND TRY_CAST(date AS DATE) IS NOT NULL
            )
            SELECT
                COALESCE(SUM(CASE WHEN age_days <= 30 THEN amount_paise ELSE 0 END), 0) AS bucket_0_30,
                COALESCE(SUM(CASE WHEN age_days BETWEEN 31 AND 60 THEN amount_paise ELSE 0 END), 0) AS bucket_31_60,
                COALESCE(SUM(CASE WHEN age_days BETWEEN 61 AND 90 THEN amount_paise ELSE 0 END), 0) AS bucket_61_90,
                COALESCE(SUM(CASE WHEN age_days BETWEEN 91 AND 180 THEN amount_paise ELSE 0 END), 0) AS bucket_91_180,
                COALESCE(SUM(CASE WHEN age_days > 180 THEN amount_paise ELSE 0 END), 0) AS bucket_180_plus,
                COALESCE(SUM(amount_paise), 0) AS total
            FROM outstanding_sales
        """, [str(ctx.period_end)]).fetchone()

        if not result:
            return []

        buckets = {
            "0-30": result[0],
            "31-60": result[1],
            "61-90": result[2],
            "91-180": result[3],
            "180+": result[4],
            "total": result[5],
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
class ReceivablesConcentrationMetric:
    code = "receivables.concentration"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        total_row = duck.execute("""
            SELECT COALESCE(SUM(total_paise), 0) FROM mart_sales_by_party
        """).fetchone()
        total = total_row[0] if total_row else 0

        if total == 0:
            return [MetricResult(
                metric_code=self.code,
                period_start=ctx.period_start,
                period_end=ctx.period_end,
                value_numeric=0.0,
                value_json={"top_parties": [], "total_paise": 0},
                unit="percent",
                version=self.version,
            )]

        top_parties = duck.execute("""
            SELECT party, total_paise, voucher_count
            FROM mart_sales_by_party
            ORDER BY total_paise DESC
            LIMIT 10
        """).fetchall()

        parties_list = []
        for party, paise, count in top_parties:
            parties_list.append({
                "party": party,
                "total_paise": paise,
                "percentage": round(paise * 100.0 / total, 2) if total else 0,
                "voucher_count": count,
            })

        top_3_pct = sum(p["percentage"] for p in parties_list[:3])

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=top_3_pct,
            value_json={"top_parties": parties_list, "total_paise": total, "top_3_pct": top_3_pct},
            unit="percent",
            version=self.version,
        )]
