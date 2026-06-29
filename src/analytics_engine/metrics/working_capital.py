"""Working capital metrics — current ratio, net working capital."""

from __future__ import annotations

import duckdb

from analytics_engine.core.types import MetricResult
from analytics_engine.metrics.base import MetricContext, metric_registry


@metric_registry.register
class CurrentRatioMetric:
    code = "working_capital.current_ratio"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        result = duck.execute("""
            SELECT
                COALESCE(SUM(CASE
                    WHEN standard_category IN ('cash', 'bank', 'sundry_debtors', 'current_asset', 'loans_advances')
                    THEN closing_balance_paise ELSE 0
                END), 0) AS current_assets,
                COALESCE(SUM(CASE
                    WHEN standard_category IN ('sundry_creditors', 'current_liability', 'duties_taxes')
                    THEN ABS(closing_balance_paise) ELSE 0
                END), 0) AS current_liabilities
            FROM mart_ledgers
        """).fetchone()

        if not result:
            return []

        ca, cl = result[0], result[1]
        ratio = ca / cl if cl > 0 else None

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=round(ratio, 4) if ratio is not None else None,
            value_json={"current_assets_paise": ca, "current_liabilities_paise": cl},
            unit="ratio",
            version=self.version,
        )]


@metric_registry.register
class NetWorkingCapitalMetric:
    code = "working_capital.net_working_capital"
    version = 1

    def compute(self, duck: duckdb.DuckDBPyConnection, ctx: MetricContext) -> list[MetricResult]:
        result = duck.execute("""
            SELECT
                COALESCE(SUM(CASE
                    WHEN standard_category IN ('cash', 'bank', 'sundry_debtors', 'current_asset', 'loans_advances')
                    THEN closing_balance_paise ELSE 0
                END), 0) AS current_assets,
                COALESCE(SUM(CASE
                    WHEN standard_category IN ('sundry_creditors', 'current_liability', 'duties_taxes')
                    THEN ABS(closing_balance_paise) ELSE 0
                END), 0) AS current_liabilities
            FROM mart_ledgers
        """).fetchone()

        if not result:
            return []

        ca, cl = result[0], result[1]
        nwc = ca - cl

        return [MetricResult(
            metric_code=self.code,
            period_start=ctx.period_start,
            period_end=ctx.period_end,
            value_numeric=float(nwc),
            value_json={"current_assets_paise": ca, "current_liabilities_paise": cl, "nwc_paise": nwc},
            unit="inr_paise",
            version=self.version,
        )]
