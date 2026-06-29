"""Loan recommendation engine — rules-based, pluggable for future ML scoring."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from analytics_engine.core.config import ConfigLoader
from analytics_engine.core.types import LoanRequirement, MetricResult
from analytics_engine.db.models import LoanRecommendation
from analytics_engine.loan.evidence import build_evidence_chain
from analytics_engine.loan.rules import evaluate_rule
from analytics_engine.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)


class LoanEngine:
    def __init__(self, session: Session, config_loader: ConfigLoader):
        self._session = session
        self._config = config_loader

    def evaluate(self, ctx: PipelineContext) -> list[LoanRequirement]:
        if ctx.profile is None:
            return []

        policy = self._config.get_loan_policy(ctx.vertical)
        if not policy:
            return []

        products = policy.products
        requirements = []

        for product_def in products:
            req = self._evaluate_product(product_def, ctx)
            if req:
                requirements.append(req)
                self._persist(ctx, req)

        self._session.commit()
        logger.info("Loan engine produced %d recommendations for client %s", len(requirements), ctx.client_id)
        return requirements

    def _evaluate_product(self, product_def: dict, ctx: PipelineContext) -> LoanRequirement | None:
        code = product_def["code"]
        rules = product_def.get("eligibility_rules", [])

        results = []
        for rule_def in rules:
            er = evaluate_rule(rule_def, ctx.metric_results, ctx.alerts_raised)
            results.append(er)

        # Weighted score
        total_weight = sum(r.weight for r in results)
        if total_weight == 0:
            return None

        weighted_score = sum(r.weight for r in results if r.passed) / total_weight

        if weighted_score < 0.5:
            return None

        # Compute recommended amount
        amount = self._compute_amount(product_def, ctx.metric_results)
        if amount is None or amount <= 0:
            return None

        # Clamp to min/max
        min_amt = product_def.get("min_amount_paise", 0)
        max_amt = product_def.get("max_amount_paise", 5_000_000_000)
        amount = max(min_amt, min(amount, max_amt))

        confidence = "high" if weighted_score >= 0.8 else "medium" if weighted_score >= 0.6 else "low"

        evidence = build_evidence_chain(code, amount, ctx.metric_results, results)

        failed_rules = [r.rule_name for r in results if not r.passed]
        rationale = f"Based on your financial data, you qualify for {product_def['name']}."
        if failed_rules:
            rationale += f" Note: {', '.join(failed_rules)} need improvement."

        return LoanRequirement(
            product_type=code,
            recommended_amount_paise=amount,
            confidence=confidence,
            rationale=rationale,
            evidence_chain=evidence,
            eligibility_results=results,
            valid_until=date.today() + timedelta(days=30),
        )

    def _compute_amount(self, product_def: dict, metrics: dict[str, MetricResult]) -> int | None:
        formula = product_def.get("amount_formula", "")

        if "net_working_capital" in formula:
            nwc = metrics.get("working_capital.net_working_capital")
            if nwc and nwc.value_json:
                nwc_paise = nwc.value_json.get("nwc_paise", 0)
                if nwc_paise > 0:
                    return int(nwc_paise * 0.75)

        if "eligible_receivables" in formula:
            aging = metrics.get("receivables.aging_buckets")
            if aging and aging.value_json:
                total = aging.value_json.get("total", 0)
                overdue = aging.value_json.get("91-180", 0) + aging.value_json.get("180+", 0)
                eligible = total - overdue
                if eligible > 0:
                    return int(eligible * 0.80)

        return None

    def _persist(self, ctx: PipelineContext, req: LoanRequirement) -> None:
        # Expire previous active recommendations for same product
        (
            self._session.query(LoanRecommendation)
            .filter_by(client_id=ctx.client_id, product_type=req.product_type, status="active")
            .update({"status": "expired"})
        )

        evidence_data = [
            {"source_type": e.source_type, "source_id": e.source_id,
             "description": e.description, "value": e.value}
            for e in req.evidence_chain
        ]
        eligibility_data = [
            {"rule_code": e.rule_code, "rule_name": e.rule_name,
             "passed": e.passed, "detail": e.detail, "weight": e.weight}
            for e in req.eligibility_results
        ]

        record = LoanRecommendation(
            client_id=ctx.client_id,
            product_type=req.product_type,
            recommended_amount_paise=req.recommended_amount_paise,
            confidence=req.confidence,
            rationale=req.rationale,
            evidence_json=evidence_data,
            eligibility_json=eligibility_data,
            valid_until=req.valid_until,
            pipeline_run_id=ctx.run_id,
        )
        self._session.add(record)
