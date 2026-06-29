"""Layer 3: Staging — build in-memory DuckDB marts from Postgres data."""

from __future__ import annotations

import logging

import duckdb
from sqlalchemy.orm import Session

from analytics_engine.core.amount import parse_amount_to_paise
from analytics_engine.db.models import ClassifiedLedger, Party
from analytics_engine.db.public_models import Voucher
from analytics_engine.pipeline.context import PipelineContext

logger = logging.getLogger(__name__)


class L3Staging:
    def __init__(self, session: Session):
        self._session = session

    def execute(self, ctx: PipelineContext, duck: duckdb.DuckDBPyConnection) -> None:
        self._build_mart_vouchers(ctx, duck)
        self._build_mart_ledgers(ctx, duck)
        self._build_mart_parties(ctx, duck)
        self._build_derived_marts(duck)
        logger.info("L3 staging complete for client %s", ctx.client_id)

    def _build_mart_vouchers(self, ctx: PipelineContext, duck: duckdb.DuckDBPyConnection) -> None:
        vouchers = (
            self._session.query(Voucher)
            .filter(Voucher.tenant_id.in_(ctx.tenant_ids))
            .all()
        )

        rows = []
        for v in vouchers:
            amount_paise = parse_amount_to_paise(v.amount)
            rows.append({
                "id": v.id,
                "voucher_guid": v.voucher_guid,
                "voucher_type": v.voucher_type,
                "voucher_number": v.voucher_number,
                "date": v.date,
                "party": v.party or "",
                "amount_paise": amount_paise or 0,
                "narration": v.narration or "",
                "company_guid": v.company_guid,
            })

        if rows:
            duck.execute("""
                CREATE TABLE mart_vouchers AS
                SELECT * FROM (
                    VALUES
                    (0, '', '', '', '', '', CAST(0 AS BIGINT), '', '')
                ) AS t(id, voucher_guid, voucher_type, voucher_number,
                    date, party, amount_paise, narration, company_guid)
                WHERE 1=0
            """)
            duck.executemany(
                "INSERT INTO mart_vouchers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (r["id"], r["voucher_guid"], r["voucher_type"], r["voucher_number"],
                     r["date"], r["party"], r["amount_paise"], r["narration"], r["company_guid"])
                    for r in rows
                ],
            )
        else:
            duck.execute("""
                CREATE TABLE mart_vouchers (
                    id INTEGER, voucher_guid VARCHAR, voucher_type VARCHAR,
                    voucher_number VARCHAR, date VARCHAR, party VARCHAR,
                    amount_paise BIGINT, narration VARCHAR, company_guid VARCHAR
                )
            """)

        logger.debug("mart_vouchers: %d rows", len(rows))

    def _build_mart_ledgers(self, ctx: PipelineContext, duck: duckdb.DuckDBPyConnection) -> None:
        ledgers = (
            self._session.query(ClassifiedLedger)
            .filter_by(client_id=ctx.client_id)
            .all()
        )

        duck.execute("""
            CREATE TABLE mart_ledgers (
                ledger_id INTEGER, ledger_guid VARCHAR, name VARCHAR,
                standard_category VARCHAR, is_bank_account BOOLEAN, is_cash_account BOOLEAN,
                opening_balance_paise BIGINT, closing_balance_paise BIGINT
            )
        """)

        if ledgers:
            duck.executemany(
                "INSERT INTO mart_ledgers VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (l.ledger_id, l.ledger_guid, l.name, l.standard_category,
                     l.is_bank_account, l.is_cash_account,
                     l.opening_balance_paise or 0, l.closing_balance_paise or 0)
                    for l in ledgers
                ],
            )

        logger.debug("mart_ledgers: %d rows", len(ledgers))

    def _build_mart_parties(self, ctx: PipelineContext, duck: duckdb.DuckDBPyConnection) -> None:
        parties = (
            self._session.query(Party)
            .filter_by(client_id=ctx.client_id)
            .all()
        )

        duck.execute("""
            CREATE TABLE mart_parties (
                party_id VARCHAR, canonical_name VARCHAR, party_type VARCHAR,
                first_seen_date VARCHAR, last_seen_date VARCHAR
            )
        """)

        if parties:
            duck.executemany(
                "INSERT INTO mart_parties VALUES (?, ?, ?, ?, ?)",
                [
                    (p.party_id, p.canonical_name, p.party_type,
                     str(p.first_seen_date) if p.first_seen_date else None,
                     str(p.last_seen_date) if p.last_seen_date else None)
                    for p in parties
                ],
            )

        logger.debug("mart_parties: %d rows", len(parties))

    def _build_derived_marts(self, duck: duckdb.DuckDBPyConnection) -> None:
        # Sales by party — for concentration metrics
        duck.execute("""
            CREATE TABLE mart_sales_by_party AS
            SELECT
                party,
                SUM(amount_paise) AS total_paise,
                COUNT(*) AS voucher_count,
                MIN(date) AS first_sale_date,
                MAX(date) AS last_sale_date
            FROM mart_vouchers
            WHERE voucher_type = 'Sales' AND party != ''
            GROUP BY party
            ORDER BY total_paise DESC
        """)

        # Purchases by party
        duck.execute("""
            CREATE TABLE mart_purchases_by_party AS
            SELECT
                party,
                SUM(amount_paise) AS total_paise,
                COUNT(*) AS voucher_count,
                MIN(date) AS first_purchase_date,
                MAX(date) AS last_purchase_date
            FROM mart_vouchers
            WHERE voucher_type = 'Purchase' AND party != ''
            GROUP BY party
            ORDER BY total_paise DESC
        """)

        # Monthly summary by voucher type
        duck.execute("""
            CREATE TABLE mart_monthly_summary AS
            SELECT
                voucher_type,
                STRFTIME(TRY_CAST(date AS DATE), '%Y-%m') AS month,
                SUM(amount_paise) AS total_paise,
                COUNT(*) AS voucher_count
            FROM mart_vouchers
            WHERE TRY_CAST(date AS DATE) IS NOT NULL
            GROUP BY voucher_type, STRFTIME(TRY_CAST(date AS DATE), '%Y-%m')
            ORDER BY month
        """)

        logger.debug("Derived marts built")
