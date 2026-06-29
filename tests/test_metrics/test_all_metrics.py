"""Tests for all metric computations against seeded DuckDB data."""

from analytics_engine.metrics import metric_registry


class TestMetricRegistry:
    def test_all_metrics_registered(self):
        codes = metric_registry.all_codes()
        assert "receivables.dso" in codes
        assert "payables.dpo" in codes
        assert "working_capital.current_ratio" in codes
        assert "revenue.monthly_trend" in codes
        assert "cash_flow.net_operating" in codes
        assert "ccc.cash_conversion_cycle" in codes
        assert "inventory.dio" in codes
        assert "inventory.stock_turnover" in codes
        assert len(codes) >= 12  # All registered metrics


class TestDSOMetric:
    def test_dso_computation(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("receivables.dso")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.metric_code == "receivables.dso"
        assert r.unit == "days"
        assert r.value_numeric is not None
        assert r.value_numeric > 0  # DSO should be positive with outstanding debtors


class TestReceivablesAging:
    def test_aging_buckets(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("receivables.aging_buckets")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.value_json is not None
        assert "0-30" in r.value_json
        assert "total" in r.value_json
        assert r.value_json["total"] > 0


class TestReceivablesConcentration:
    def test_concentration(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("receivables.concentration")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.value_json is not None
        assert "top_parties" in r.value_json
        assert len(r.value_json["top_parties"]) > 0
        # ABC Enterprises should be top (3 sales = 14L out of 21.5L)
        top = r.value_json["top_parties"][0]
        assert top["party"] == "ABC Enterprises"
        assert top["percentage"] > 50


class TestDPOMetric:
    def test_dpo_computation(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("payables.dpo")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.unit == "days"
        assert r.value_numeric is not None
        assert r.value_numeric > 0


class TestCurrentRatio:
    def test_current_ratio(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("working_capital.current_ratio")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.unit == "ratio"
        assert r.value_numeric is not None
        # CA = cash(3L) + bank(8L) + debtors(12L) + current_asset(4L) = 27L
        # CL = creditors(7.5L) + taxes(0.8L) = 8.3L
        # Ratio should be > 1
        assert r.value_numeric > 1.0
        assert r.value_json["current_assets_paise"] > 0
        assert r.value_json["current_liabilities_paise"] > 0


class TestNetWorkingCapital:
    def test_nwc(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("working_capital.net_working_capital")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.unit == "inr_paise"
        assert r.value_json["nwc_paise"] > 0  # Should be positive (healthy)


class TestMonthlyTrend:
    def test_revenue_trend(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("revenue.monthly_trend")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.value_json is not None
        months = r.value_json["months"]
        assert len(months) == 6  # Jan through Jun
        assert all("month" in m and "total_paise" in m for m in months)


class TestMoMGrowth:
    def test_mom_growth(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("revenue.mom_growth")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.value_json is not None
        series = r.value_json["growth_series"]
        assert len(series) > 0
        # Each entry should have growth_pct
        for entry in series:
            assert "month" in entry
            assert "growth_pct" in entry


class TestNetOperatingCashFlow:
    def test_cash_flow(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("cash_flow.net_operating")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.value_json is not None
        # Receipts (6L) - Payments (7.5L) = -1.5L
        assert r.value_json["inflows_paise"] == 6_00_000_00
        assert r.value_json["outflows_paise"] == 7_50_000_00
        assert r.value_json["net_cf_paise"] < 0


class TestBurnRate:
    def test_burn_rate(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("cash_flow.burn_rate")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.value_json is not None
        assert r.value_json["cash_on_hand_paise"] > 0
        assert r.value_json["monthly_burn_paise"] > 0
        assert r.value_json["runway_days"] is not None
        assert r.value_json["runway_days"] > 0


class TestCCC:
    def test_cash_conversion_cycle(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("ccc.cash_conversion_cycle")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.value_json is not None
        assert r.value_json["dso"] is not None
        assert r.value_json["dpo"] is not None
        assert r.value_json["ccc"] is not None


class TestDIO:
    def test_dio(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("inventory.dio")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        # Stock-in-Trade is classified as current_asset with "stock" in name
        r = results[0]
        assert r.unit == "days"


class TestStockTurnover:
    def test_stock_turnover(self, seeded_duck, metric_ctx):
        metric = metric_registry.get("inventory.stock_turnover")
        results = metric.compute(seeded_duck, metric_ctx)
        assert len(results) == 1
        r = results[0]
        assert r.unit == "ratio"
