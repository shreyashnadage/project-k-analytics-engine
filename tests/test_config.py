"""Tests for config loader and vertical profile resolution."""


import pytest

from analytics_engine.core.config import ConfigLoader, _deep_merge


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        assert _deep_merge(base, override) == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"x": {"a": 1, "b": 2}}
        override = {"x": {"b": 3, "c": 4}}
        assert _deep_merge(base, override) == {"x": {"a": 1, "b": 3, "c": 4}}

    def test_list_replace(self):
        base = {"items": [1, 2]}
        override = {"items": [3, 4]}
        assert _deep_merge(base, override) == {"items": [3, 4]}

    def test_list_inherit(self):
        base = {"items": ["a", "b"]}
        override = {"items": ["$inherit", "c"]}
        result = _deep_merge(base, override)
        assert result["items"] == ["a", "b", "c"]

    def test_does_not_mutate_base(self):
        base = {"x": {"a": 1}}
        override = {"x": {"b": 2}}
        _deep_merge(base, override)
        assert base == {"x": {"a": 1}}


class TestConfigLoader:
    @pytest.fixture
    def loader(self, config_dir):
        return ConfigLoader(config_dir)

    def test_load_base(self, loader):
        profile = loader.get_vertical("_base")
        assert "receivables.dso" in profile.metrics_enabled
        assert "liquidity_shortfall" in profile.detectors_enabled
        assert profile.fiscal_year_start_month == 4
        assert profile.amount_display == "indian"

    def test_trading_inherits_base(self, loader):
        profile = loader.get_vertical("trading")
        assert "receivables.dso" in profile.metrics_enabled
        assert "inventory.dio" in profile.metrics_enabled
        assert "inventory.stock_turnover" in profile.metrics_enabled

    def test_trading_overrides_detectors(self, loader):
        profile = loader.get_vertical("trading")
        assert profile.detector_overrides.get("ccc_stretch", {}).get("threshold_days") == 45

    def test_manufacturing_extends_base(self, loader):
        profile = loader.get_vertical("manufacturing")
        assert "inventory.raw_material_coverage" in profile.metrics_enabled
        assert "inventory_buildup" in profile.detectors_enabled

    def test_client_overrides(self, loader):
        overrides = {
            "detectors": {
                "overrides": {
                    "liquidity_shortfall": {"projection_horizon_days": 60}
                }
            }
        }
        profile = loader.resolve_client_config("trading", overrides)
        assert profile.detector_overrides["liquidity_shortfall"]["projection_horizon_days"] == 60
        # Base metrics still present
        assert "receivables.dso" in profile.metrics_enabled

    def test_aging_buckets(self, loader):
        profile = loader.get_vertical("_base")
        assert len(profile.aging_buckets.boundaries_days) == 6
        assert profile.aging_buckets.labels[0] == "Current"

    def test_detector_config(self, loader):
        det = loader.get_detector_config("liquidity_shortfall")
        assert det.code == "liquidity_shortfall"
        assert det.parameters["projection_horizon_days"] == 30
        assert "critical" in det.severity_rules

    def test_scheduling_config(self, loader):
        sched = loader.get_scheduling_config()
        assert sched["plan_tiers"]["trial"]["interval_minutes"] == 360
