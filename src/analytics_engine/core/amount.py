"""Parse Indian-format amount strings from Tally into integer paise.

Tally stores amounts as strings like "1,23,456.50" (Indian grouping)
or "1,234,567.50" (Western grouping) or "-50,000.00" (negative).
We convert to integer paise (1/100 rupee) to avoid floating-point errors.
"""

import re

from analytics_engine.core.exceptions import AmountParseError

_CLEANUP_RE = re.compile(r"[^\d.\-]")


def parse_amount_to_paise(raw: str | None) -> int | None:
    """Convert an amount string to integer paise.

    Returns None for None/empty input.
    Raises AmountParseError for unparseable values.

    Examples:
        "1,23,456.50"  ->  12345650
        "-50,000.00"   -> -5000000
        "1234.5"       ->   123450
        "0"            ->        0
        ""             ->     None
        None           ->     None
    """
    if raw is None:
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    negative = cleaned.startswith("-")
    if negative:
        cleaned = cleaned[1:]

    # Remove all characters except digits and decimal point
    cleaned = _CLEANUP_RE.sub("", cleaned)

    if not cleaned:
        return None

    parts = cleaned.split(".")
    if len(parts) > 2:
        raise AmountParseError(f"Multiple decimal points in amount: {raw!r}")

    integer_part = parts[0] or "0"
    decimal_part = parts[1] if len(parts) == 2 else "0"

    # Normalize decimal to exactly 2 digits (paise)
    if len(decimal_part) > 2:
        decimal_part = decimal_part[:2]
    decimal_part = decimal_part.ljust(2, "0")

    try:
        paise = int(integer_part) * 100 + int(decimal_part)
    except ValueError as e:
        raise AmountParseError(f"Cannot parse amount: {raw!r}") from e

    return -paise if negative else paise


def paise_to_rupees(paise: int) -> str:
    """Format paise as rupee string with 2 decimal places."""
    negative = paise < 0
    paise = abs(paise)
    rupees = paise // 100
    remainder = paise % 100
    result = f"{rupees}.{remainder:02d}"
    return f"-{result}" if negative else result


def paise_to_lakhs(paise: int) -> str:
    """Format paise as Indian lakhs notation (e.g., '12.35L')."""
    rupees = paise / 100
    if abs(rupees) >= 1_00_00_000:
        return f"{rupees / 1_00_00_000:.2f}Cr"
    if abs(rupees) >= 1_00_000:
        return f"{rupees / 1_00_000:.2f}L"
    if abs(rupees) >= 1_000:
        return f"{rupees / 1_000:.2f}K"
    return f"{rupees:.0f}"
