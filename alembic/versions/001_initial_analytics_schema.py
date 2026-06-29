"""Initial analytics schema.

Revision ID: 001
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

SCHEMA = "analytics"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # -- Pipeline Control --
    op.create_table(
        "sync_watermarks",
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("last_synced_id", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("client_id", "entity_type"),
        schema=SCHEMA,
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("run_id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("layer_reached", sa.SmallInteger),
        sa.Column("error_message", sa.Text),
        sa.Column("vouchers_pulled", sa.Integer, server_default="0"),
        sa.Column("metrics_computed", sa.Integer, server_default="0"),
        sa.Column("alerts_raised", sa.Integer, server_default="0"),
        schema=SCHEMA,
    )
    op.create_index("ix_pipeline_runs_client", "pipeline_runs", ["client_id", "started_at"], schema=SCHEMA)

    # -- Normalization --
    op.create_table(
        "parties",
        sa.Column("party_id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("canonical_name", sa.String(500), nullable=False),
        sa.Column("party_type", sa.String(20)),
        sa.Column("gst_number", sa.String(50)),
        sa.Column("aliases", sa.Text),
        sa.Column("first_seen_date", sa.Date),
        sa.Column("last_seen_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_parties_client", "parties", ["client_id"], schema=SCHEMA)

    op.create_table(
        "classified_ledgers",
        sa.Column("ledger_id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("ledger_guid", sa.String(255), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("tally_parent", sa.String(500)),
        sa.Column("tally_type", sa.String(100)),
        sa.Column("standard_category", sa.String(50), nullable=False),
        sa.Column("is_bank_account", sa.Boolean, server_default="false"),
        sa.Column("is_cash_account", sa.Boolean, server_default="false"),
        sa.Column("opening_balance_paise", sa.BigInteger),
        sa.Column("closing_balance_paise", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("ix_classified_ledgers_client", "classified_ledgers", ["client_id"], schema=SCHEMA)
    op.create_index("ix_classified_ledgers_category", "classified_ledgers", ["client_id", "standard_category"], schema=SCHEMA)

    # -- Metrics --
    op.create_table(
        "metric_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("metric_code", sa.String(80), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("value_numeric", sa.Float),
        sa.Column("value_json", JSONB),
        sa.Column("unit", sa.String(20)),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("pipeline_run_id", sa.String(36)),
        sa.Column("version", sa.SmallInteger, server_default="1"),
        sa.UniqueConstraint("client_id", "metric_code", "period_end", "version", name="uq_metric_snapshot_dedup"),
        schema=SCHEMA,
    )
    op.create_index("ix_metric_snapshots_lookup", "metric_snapshots", ["client_id", "metric_code", "period_end"], schema=SCHEMA)

    op.create_table(
        "benchmark_percentiles",
        sa.Column("vertical", sa.String(30), nullable=False),
        sa.Column("metric_code", sa.String(80), nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("sample_size", sa.Integer, nullable=False),
        sa.Column("p25", sa.Float),
        sa.Column("p50", sa.Float),
        sa.Column("p75", sa.Float),
        sa.Column("p90", sa.Float),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("vertical", "metric_code", "period_end"),
        schema=SCHEMA,
    )

    # -- Insights & Alerts --
    op.create_table(
        "insights",
        sa.Column("insight_id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("metric_code", sa.String(80), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("data_json", JSONB),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        schema=SCHEMA,
    )
    op.create_index("ix_insights_client", "insights", ["client_id", "created_at"], schema=SCHEMA)

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("detector_code", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("evidence_json", JSONB, nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("snoozed_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("pipeline_run_id", sa.String(36)),
        schema=SCHEMA,
    )
    op.create_index("ix_alerts_client", "alerts", ["client_id", "status", "created_at"], schema=SCHEMA)

    # -- Loan Recommendations --
    op.create_table(
        "loan_recommendations",
        sa.Column("reco_id", sa.String(36), primary_key=True),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("product_type", sa.String(30), nullable=False),
        sa.Column("recommended_amount_paise", sa.BigInteger, nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("evidence_json", JSONB, nullable=False),
        sa.Column("eligibility_json", JSONB, nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("valid_until", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("pipeline_run_id", sa.String(36)),
        schema=SCHEMA,
    )
    op.create_index("ix_loan_reco_client", "loan_recommendations", ["client_id", "status"], schema=SCHEMA)

    # -- Client Profiles --
    op.create_table(
        "client_profiles",
        sa.Column("client_id", sa.String(36), primary_key=True),
        sa.Column("vertical", sa.String(30), nullable=False, server_default="trading"),
        sa.Column("vertical_source", sa.String(20), server_default="auto"),
        sa.Column("config_overrides", JSONB),
        sa.Column("currency", sa.String(3), server_default="INR"),
        sa.Column("fiscal_year_start_month", sa.SmallInteger, server_default="4"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema=SCHEMA,
    )


def downgrade() -> None:
    for table in [
        "client_profiles", "loan_recommendations", "alerts", "insights",
        "benchmark_percentiles", "metric_snapshots", "classified_ledgers",
        "parties", "pipeline_runs", "sync_watermarks",
    ]:
        op.drop_table(table, schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
