"""Insight engine — generates plain-language insights from metrics using YAML templates."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from analytics_engine.core.types import MetricResult
from analytics_engine.insights.formatters import build_template_context

logger = logging.getLogger(__name__)


@dataclass
class InsightOutput:
    metric_code: str
    category: str
    severity: str
    title: str
    body: str
    data: dict[str, Any]


class InsightEngine:
    def __init__(self, template_dir: str | None = None, lang: str = "en"):
        if template_dir is None:
            template_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "config", "insight_templates",
            )
        self._template_dir = Path(template_dir) / lang
        self._templates: list[dict] = []
        self._load_templates()

    def _load_templates(self) -> None:
        if not self._template_dir.exists():
            logger.warning("Insight template dir not found: %s", self._template_dir)
            return

        for yaml_file in sorted(self._template_dir.glob("*.yaml")):
            with open(yaml_file) as f:
                data = yaml.safe_load(f) or {}
            category = data.get("category", yaml_file.stem)
            for tmpl in data.get("templates", []):
                tmpl["_category"] = category
                self._templates.append(tmpl)

    def generate(self, metrics: dict[str, MetricResult]) -> list[InsightOutput]:
        insights = []

        for tmpl in self._templates:
            metric_code = tmpl.get("metric_code", "")
            metric = metrics.get(metric_code)
            if not metric:
                continue

            ctx = build_template_context(metric_code, metric.value_numeric, metric.value_json)
            severity = self._evaluate_severity(tmpl.get("severity_rules", {}), ctx)
            if severity is None:
                continue

            messages = tmpl.get("messages", {}).get(severity)
            if not messages:
                continue

            try:
                title = messages["title"].format(**ctx)
                body = messages["body"].format(**ctx)
            except (KeyError, ValueError) as e:
                logger.warning("Template render failed for %s/%s: %s", metric_code, severity, e)
                continue

            insights.append(InsightOutput(
                metric_code=metric_code,
                category=tmpl["_category"],
                severity=severity,
                title=title,
                body=body,
                data=ctx,
            ))

        return insights

    def _evaluate_severity(self, rules: dict[str, str], ctx: dict) -> str | None:
        for severity in ("critical", "warning", "info"):
            expr = rules.get(severity)
            if not expr:
                continue
            try:
                eval_ctx = {**ctx, "true": True, "false": False}
                if eval(expr, {"__builtins__": {}}, eval_ctx):  # noqa: S307
                    return severity
            except Exception:
                continue
        return None
