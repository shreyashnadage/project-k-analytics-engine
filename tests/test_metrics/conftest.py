"""Shared fixtures for metric tests — seeds a DuckDB with sample Tally data."""

from datetime import date

import duckdb
import pytest

from analytics_engine.metrics.base import MetricContext


@pytest.fixture
def metric_ctx() -> MetricContext:
    return MetricContext(
        period_start=date(2025, 1, 1),
        period_end=date(2025, 6, 30),
    )


@pytest.fixture
def seeded_duck() -> duckdb.DuckDBPyConnection:
    """DuckDB with realistic MSME Tally data pre-loaded."""
    duck = duckdb.connect(":memory:")

    # mart_vouchers
    duck.execute("""
        CREATE TABLE mart_vouchers (
            id INTEGER, voucher_guid VARCHAR, voucher_type VARCHAR,
            voucher_number VARCHAR, date VARCHAR, party VARCHAR,
            amount_paise BIGINT, narration VARCHAR, company_guid VARCHAR
        )
    """)
    # Sales vouchers
    sales = [
        (1, 'v1', 'Sales', 'S001', '2025-01-15', 'ABC Enterprises', 5_00_000_00, '', 'co1'),
        (2, 'v2', 'Sales', 'S002', '2025-02-10', 'ABC Enterprises', 3_00_000_00, '', 'co1'),
        (3, 'v3', 'Sales', 'S003', '2025-03-05', 'XYZ Trading', 2_00_000_00, '', 'co1'),
        (4, 'v4', 'Sales', 'S004', '2025-04-20', 'PQR Industries', 4_00_000_00, '', 'co1'),
        (5, 'v5', 'Sales', 'S005', '2025-05-12', 'ABC Enterprises', 6_00_000_00, '', 'co1'),
        (6, 'v6', 'Sales', 'S006', '2025-06-01', 'MNO Stores', 1_50_000_00, '', 'co1'),
    ]
    # Purchase vouchers
    purchases = [
        (7, 'v7', 'Purchase', 'P001', '2025-01-20', 'Supplier A', 3_00_000_00, '', 'co1'),
        (8, 'v8', 'Purchase', 'P002', '2025-03-15', 'Supplier B', 2_50_000_00, '', 'co1'),
        (9, 'v9', 'Purchase', 'P003', '2025-05-01', 'Supplier A', 4_00_000_00, '', 'co1'),
    ]
    # Payment and Receipt vouchers
    payments = [
        (10, 'v10', 'Payment', 'PAY01', '2025-02-15', 'Supplier A', 2_00_000_00, '', 'co1'),
        (11, 'v11', 'Payment', 'PAY02', '2025-04-10', 'Supplier B', 2_50_000_00, '', 'co1'),
        (12, 'v12', 'Payment', 'PAY03', '2025-06-15', 'Supplier A', 3_00_000_00, '', 'co1'),
    ]
    receipts = [
        (13, 'v13', 'Receipt', 'R01', '2025-03-01', 'ABC Enterprises', 4_00_000_00, '', 'co1'),
        (14, 'v14', 'Receipt', 'R02', '2025-05-20', 'XYZ Trading', 2_00_000_00, '', 'co1'),
    ]

    for batch in [sales, purchases, payments, receipts]:
        duck.executemany(
            "INSERT INTO mart_vouchers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", batch
        )

    # mart_ledgers
    duck.execute("""
        CREATE TABLE mart_ledgers (
            ledger_id INTEGER, ledger_guid VARCHAR, name VARCHAR,
            standard_category VARCHAR, is_bank_account BOOLEAN, is_cash_account BOOLEAN,
            opening_balance_paise BIGINT, closing_balance_paise BIGINT
        )
    """)
    ledgers = [
        (1, 'l1', 'Cash', 'cash', False, True, 2_00_000_00, 3_00_000_00),
        (2, 'l2', 'HDFC Bank', 'bank', True, False, 5_00_000_00, 8_00_000_00),
        (3, 'l3', 'ABC Enterprises', 'sundry_debtors', False, False, 0, 10_00_000_00),
        (4, 'l4', 'XYZ Trading', 'sundry_debtors', False, False, 0, 2_00_000_00),
        (5, 'l5', 'Supplier A', 'sundry_creditors', False, False, 0, -5_00_000_00),
        (6, 'l6', 'Supplier B', 'sundry_creditors', False, False, 0, -2_50_000_00),
        (7, 'l7', 'Stock-in-Trade', 'current_asset', False, False, 3_00_000_00, 4_00_000_00),
        (8, 'l8', 'Input GST', 'duties_taxes', False, False, 0, 50_000_00),
        (9, 'l9', 'Output GST', 'duties_taxes', False, False, 0, -80_000_00),
    ]
    duck.executemany(
        "INSERT INTO mart_ledgers VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ledgers
    )

    # mart_parties
    duck.execute("""
        CREATE TABLE mart_parties (
            party_id VARCHAR, canonical_name VARCHAR, party_type VARCHAR,
            first_seen_date VARCHAR, last_seen_date VARCHAR
        )
    """)

    # Derived marts
    duck.execute("""
        CREATE TABLE mart_sales_by_party AS
        SELECT party, SUM(amount_paise) AS total_paise, COUNT(*) AS voucher_count,
               MIN(date) AS first_sale_date, MAX(date) AS last_sale_date
        FROM mart_vouchers WHERE voucher_type = 'Sales' AND party != ''
        GROUP BY party ORDER BY total_paise DESC
    """)

    duck.execute("""
        CREATE TABLE mart_purchases_by_party AS
        SELECT party, SUM(amount_paise) AS total_paise, COUNT(*) AS voucher_count,
               MIN(date) AS first_purchase_date, MAX(date) AS last_purchase_date
        FROM mart_vouchers WHERE voucher_type = 'Purchase' AND party != ''
        GROUP BY party ORDER BY total_paise DESC
    """)

    duck.execute("""
        CREATE TABLE mart_monthly_summary AS
        SELECT voucher_type, STRFTIME(TRY_CAST(date AS DATE), '%Y-%m') AS month,
               SUM(amount_paise) AS total_paise, COUNT(*) AS voucher_count
        FROM mart_vouchers WHERE TRY_CAST(date AS DATE) IS NOT NULL
        GROUP BY voucher_type, STRFTIME(TRY_CAST(date AS DATE), '%Y-%m')
        ORDER BY month
    """)

    yield duck
    duck.close()
