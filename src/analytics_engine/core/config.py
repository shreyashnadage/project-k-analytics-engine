"""Configuration loader with YAML inheritance and deep-merge.

Config cascade: _base.yaml -> vertical.yaml -> client_overrides (JSONB)
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from analytics_engine.core.exceptions import ConfigError
from analytics_engine.core.types import AgingBucketConfig


@dataclass(frozen=True)
class VerticalProfile:
    name: str
    metrics_enabled: list[str]
    detectors_enabled: list[str]
    detector_overrides: dict[str, dict[str, Any]]
    ledger_classification: dict[str, list[str]]
    aging_buckets: AgingBucketConfig
    fiscal_year_start_month: int
    amount_display: str


@dataclass(frozen=True)
class DetectorConfig:
    code: str
    name: str
    description: str
    parameters: dict[str, Any]
    severity_rules: dict[str, str]

    def merge(self, overrides: dict[str, Any]) -> DetectorConfig:
        if not overrides:
            return self
        params = {**self.parameters, **overrides}
        return DetectorConfig(
            code=self.code,
            name=self.name,
            description=self.description,
            parameters=params,
            severity_rules=self.severity_rules,
        )


@dataclass(frozen=True)
class LoanPolicy:
    vertical: str
    products: list[dict[str, Any]]


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Lists with '$inherit' prepend base items."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            if "$inherit" in value:
                inherited = copy.deepcopy(result[key])
                result[key] = inherited + [v for v in value if v != "$inherit"]
            else:
                result[key] = copy.deepcopy(value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data or {}


class ConfigLoader:
    def __init__(self, config_dir: Path | str | None = None):
        if config_dir is None:
            config_dir = os.getenv("CONFIG_DIR", str(Path(__file__).resolve().parents[3] / "config"))
        self._config_dir = Path(config_dir)
        self._vertical_cache: dict[str, dict] = {}

    def _load_vertical_raw(self, name: str) -> dict:
        if name in self._vertical_cache:
            return self._vertical_cache[name]

        path = self._config_dir / "verticals" / f"{name}.yaml"
        data = _load_yaml(path)

        extends = data.pop("extends", None)
        if extends:
            parent = self._load_vertical_raw(extends)
            data = _deep_merge(parent, data)

        self._vertical_cache[name] = data
        return data

    def get_vertical(self, name: str) -> VerticalProfile:
        raw = self._load_vertical_raw(name)
        metrics = raw.get("metrics", {})
        detectors = raw.get("detectors", {})
        aging = raw.get("aging_buckets", {})

        return VerticalProfile(
            name=name,
            metrics_enabled=metrics.get("enabled", []),
            detectors_enabled=detectors.get("enabled", []),
            detector_overrides=detectors.get("overrides", {}),
            ledger_classification=raw.get("ledger_classification", {}),
            aging_buckets=AgingBucketConfig(
                boundaries_days=aging.get("boundaries_days", [0, 30, 60, 90, 180, 365]),
                labels=aging.get("labels", ["Current", "1-30", "31-60", "61-90", "91-180", "180+"]),
            ),
            fiscal_year_start_month=raw.get("fiscal_year", {}).get("start_month", 4),
            amount_display=raw.get("amount_format", {}).get("display", "indian"),
        )

    def resolve_client_config(
        self, vertical: str, client_overrides: dict[str, Any] | None
    ) -> VerticalProfile:
        raw = self._load_vertical_raw(vertical)
        if client_overrides:
            raw = _deep_merge(raw, client_overrides)

        metrics = raw.get("metrics", {})
        detectors = raw.get("detectors", {})
        aging = raw.get("aging_buckets", {})

        return VerticalProfile(
            name=vertical,
            metrics_enabled=metrics.get("enabled", []),
            detectors_enabled=detectors.get("enabled", []),
            detector_overrides=detectors.get("overrides", {}),
            ledger_classification=raw.get("ledger_classification", {}),
            aging_buckets=AgingBucketConfig(
                boundaries_days=aging.get("boundaries_days", [0, 30, 60, 90, 180, 365]),
                labels=aging.get("labels", ["Current", "1-30", "31-60", "61-90", "91-180", "180+"]),
            ),
            fiscal_year_start_month=raw.get("fiscal_year", {}).get("start_month", 4),
            amount_display=raw.get("amount_format", {}).get("display", "indian"),
        )

    def get_detector_config(self, code: str) -> DetectorConfig:
        path = self._config_dir / "detectors" / f"{code}.yaml"
        raw = _load_yaml(path)
        return DetectorConfig(
            code=raw.get("code", code),
            name=raw.get("name", code),
            description=raw.get("description", ""),
            parameters=raw.get("parameters", {}),
            severity_rules=raw.get("severity_rules", {}),
        )

    def get_loan_policy(self, vertical: str) -> LoanPolicy:
        path = self._config_dir / "loan_policies" / f"{vertical}.yaml"
        if not path.exists():
            path = self._config_dir / "loan_policies" / "_base.yaml"
        raw = _load_yaml(path)

        extends = raw.pop("extends", None)
        if extends:
            parent_path = self._config_dir / "loan_policies" / f"{extends}.yaml"
            parent = _load_yaml(parent_path)
            raw = _deep_merge(parent, raw)

        return LoanPolicy(
            vertical=vertical,
            products=raw.get("products", []),
        )

    def get_scheduling_config(self) -> dict[str, Any]:
        path = self._config_dir / "scheduling.yaml"
        return _load_yaml(path)

    def clear_cache(self) -> None:
        self._vertical_cache.clear()
