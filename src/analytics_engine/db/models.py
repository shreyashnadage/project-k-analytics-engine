"""Analytics schema ORM models — tables owned by the analytics engine."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

ANALYTICS_SCHEMA = "analytics"

analytics_metadata = MetaData(schema=ANALYTICS_SCHEMA)


class AnalyticsBase(DeclarativeBase):
    metadata = analytics_metadata


# ── Pipeline Control ──────────────────────────────────────────────────────

class SyncWatermark(AnalyticsBase):
    __tablename__ = "sync_watermarks"

    client_id = Column(String(36), primary_key=True)
    entity_type = Column(String(30), primary_key=True)  # 'voucher', 'ledger', etc.
    last_synced_id = Column(Integer, nullable=False, default=0)
    last_synced_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PipelineRun(AnalyticsBase):
    __tablename__ = "pipeline_runs"

    run_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(36), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True))
    status = Column(String(20), nullable=False, default="running")
    layer_reached = Column(SmallInteger)
    error_message = Column(Text)
    vouchers_pulled = Column(Integer, default=0)
    metrics_computed = Column(Integer, default=0)
    alerts_raised = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_pipeline_runs_client", "client_id", "started_at"),
    )


# ── Normalization ─────────────────────────────────────────────────────────

class Party(AnalyticsBase):
    __tablename__ = "parties"

    party_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(36), nullable=False, index=True)
    canonical_name = Column(String(500), nullable=False)
    party_type = Column(String(20))  # customer, supplier, both, unknown
    gst_number = Column(String(50))
    aliases = Column(Text)  # JSON array of raw name variants
    first_seen_date = Column(Date)
    last_seen_date = Column(Date)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ClassifiedLedger(AnalyticsBase):
    __tablename__ = "classified_ledgers"

    ledger_id = Column(Integer, primary_key=True)  # matches public.ledgers.id
    client_id = Column(String(36), nullable=False, index=True)
    ledger_guid = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    tally_parent = Column(String(500))
    tally_type = Column(String(100))
    standard_category = Column(String(50), nullable=False)
    is_bank_account = Column(Boolean, default=False)
    is_cash_account = Column(Boolean, default=False)
    opening_balance_paise = Column(BigInteger)
    closing_balance_paise = Column(BigInteger)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_classified_ledgers_category", "client_id", "standard_category"),
    )


# ── Metrics ───────────────────────────────────────────────────────────────

class MetricSnapshot(AnalyticsBase):
    __tablename__ = "metric_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(36), nullable=False)
    metric_code = Column(String(80), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    value_numeric = Column(Float)
    value_json = Column(JSONB)
    unit = Column(String(20))
    computed_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    pipeline_run_id = Column(String(36))
    version = Column(SmallInteger, default=1)

    __table_args__ = (
        UniqueConstraint("client_id", "metric_code", "period_end", "version",
                         name="uq_metric_snapshot_dedup"),
        Index("ix_metric_snapshots_lookup", "client_id", "metric_code", "period_end"),
    )


class BenchmarkPercentile(AnalyticsBase):
    __tablename__ = "benchmark_percentiles"

    vertical = Column(String(30), primary_key=True)
    metric_code = Column(String(80), primary_key=True)
    period_end = Column(Date, primary_key=True)
    sample_size = Column(Integer, nullable=False)
    p25 = Column(Float)
    p50 = Column(Float)
    p75 = Column(Float)
    p90 = Column(Float)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Insights & Alerts ─────────────────────────────────────────────────────

class Insight(AnalyticsBase):
    __tablename__ = "insights"

    insight_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(36), nullable=False)
    metric_code = Column(String(80), nullable=False)
    category = Column(String(30), nullable=False)
    severity = Column(String(10), nullable=False)
    title = Column(String(300), nullable=False)
    body = Column(Text, nullable=False)
    data_json = Column(JSONB)
    period_end = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True))
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_insights_client", "client_id", "created_at"),
    )


class AlertRecord(AnalyticsBase):
    __tablename__ = "alerts"

    alert_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(36), nullable=False)
    detector_code = Column(String(80), nullable=False)
    severity = Column(String(10), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    evidence_json = Column(JSONB, nullable=False)
    status = Column(String(20), default="open")
    snoozed_until = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True))
    pipeline_run_id = Column(String(36))

    __table_args__ = (
        Index("ix_alerts_client", "client_id", "status", "created_at"),
    )


# ── Loan Recommendations ─────────────────────────────────────────────────

class LoanRecommendation(AnalyticsBase):
    __tablename__ = "loan_recommendations"

    reco_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id = Column(String(36), nullable=False)
    product_type = Column(String(30), nullable=False)
    recommended_amount_paise = Column(BigInteger, nullable=False)
    confidence = Column(String(10), nullable=False)
    rationale = Column(Text, nullable=False)
    evidence_json = Column(JSONB, nullable=False)
    eligibility_json = Column(JSONB, nullable=False)
    status = Column(String(20), default="active")
    valid_until = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    pipeline_run_id = Column(String(36))

    __table_args__ = (
        Index("ix_loan_reco_client", "client_id", "status"),
    )


# ── Client Config ─────────────────────────────────────────────────────────

class ClientProfile(AnalyticsBase):
    __tablename__ = "client_profiles"

    client_id = Column(String(36), primary_key=True)
    vertical = Column(String(30), nullable=False, default="trading")
    vertical_source = Column(String(20), default="auto")
    config_overrides = Column(JSONB)
    currency = Column(String(3), default="INR")
    fiscal_year_start_month = Column(SmallInteger, default=4)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
