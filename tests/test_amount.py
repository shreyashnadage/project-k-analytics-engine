"""Tests for Indian amount string parsing."""

import pytest

from analytics_engine.core.amount import (
    paise_to_lakhs,
    paise_to_rupees,
    parse_amount_to_paise,
)
from analytics_engine.core.exceptions import AmountParseError


class TestParseAmountToPaise:
    def test_indian_format(self):
        assert parse_amount_to_paise("1,23,456.50") == 12345650

    def test_western_format(self):
        assert parse_amount_to_paise("1,234,567.50") == 123456750

    def test_negative(self):
        assert parse_amount_to_paise("-50,000.00") == -5000000

    def test_no_commas(self):
        assert parse_amount_to_paise("1234.50") == 123450

    def test_integer_only(self):
        assert parse_amount_to_paise("5000") == 500000

    def test_zero(self):
        assert parse_amount_to_paise("0") == 0

    def test_single_decimal(self):
        assert parse_amount_to_paise("100.5") == 10050

    def test_three_decimals_truncated(self):
        assert parse_amount_to_paise("100.999") == 10099

    def test_none_returns_none(self):
        assert parse_amount_to_paise(None) is None

    def test_empty_returns_none(self):
        assert parse_amount_to_paise("") is None

    def test_whitespace_returns_none(self):
        assert parse_amount_to_paise("   ") is None

    def test_multiple_decimals_raises(self):
        with pytest.raises(AmountParseError):
            parse_amount_to_paise("1.2.3")

    def test_large_amount(self):
        # 10,00,00,000 = 10 crore = 100,000,000 rupees = 10,000,000,000 paise
        assert parse_amount_to_paise("10,00,00,000.00") == 10_000_000_000


class TestPaiseToRupees:
    def test_basic(self):
        assert paise_to_rupees(12345650) == "123456.50"

    def test_zero(self):
        assert paise_to_rupees(0) == "0.00"

    def test_negative(self):
        assert paise_to_rupees(-5000000) == "-50000.00"

    def test_small(self):
        assert paise_to_rupees(50) == "0.50"


class TestPaiseToLakhs:
    def test_crores(self):
        # 10 crore rupees = 10,00,00,000 rupees = 10_000_000_000 paise
        assert paise_to_lakhs(10_000_000_000) == "10.00Cr"

    def test_lakhs(self):
        assert paise_to_lakhs(1234560000) == "1.23Cr"

    def test_thousands(self):
        assert paise_to_lakhs(500000) == "5.00K"

    def test_small(self):
        assert paise_to_lakhs(5000) == "50"
