"""
Hard filters for the MVP value-investing screener.

MVP purpose:
- Apply conservative pass/fail rules before ranking stocks.
- Keep filter logic separate from scoring logic.
"""

from __future__ import annotations

from typing import Any


FINANCIAL_SECTOR_KEYWORDS = [
    "financial",
    "bank",
    "insurance",
    "capital markets",
    "asset management",
]


def to_float(value: Any) -> float | None:
    """Convert a value to float when possible."""
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_financial_sector(values: dict[str, Any]) -> bool:
    """Return True if company appears to be a bank/insurance/financial company."""
    sector = str(values.get("sector") or "").lower()
    industry = str(values.get("industry") or "").lower()

    combined = f"{sector} {industry}"

    return any(keyword in combined for keyword in FINANCIAL_SECTOR_KEYWORDS)


def add_filter_result(
    results: list[dict[str, Any]],
    filter_name: str,
    passed: bool,
    reason: str,
) -> None:
    """Append one hard-filter result."""
    results.append(
        {
            "filter_name": filter_name,
            "passed": passed,
            "reason": reason,
        }
    )


def run_hard_filters(values: dict[str, Any]) -> dict[str, Any]:
    """
    Run MVP hard filters.

    Rules:
    - market cap above $1B equivalent where available
    - positive earnings
    - positive operating margin
    - debt/equity below 1.5 unless bank/insurance/financial sector
    - P/E greater than 0 and less than 50

    Returns:
    - overall pass/fail
    - detailed filter results
    """
    results: list[dict[str, Any]] = []

    market_cap = to_float(values.get("market_cap"))
    eps_ttm = to_float(values.get("eps_ttm"))
    earnings_share = to_float(values.get("earnings_share"))
    operating_margin = to_float(values.get("operating_margin_ttm"))
    debt_equity = to_float(values.get("debt_equity"))
    pe_ttm = to_float(values.get("pe_ttm"))

    financial_sector = is_financial_sector(values)

    # Market cap filter
    if market_cap is None:
        add_filter_result(
            results,
            "market_cap_above_1b",
            True,
            "Market cap is missing; allowed for MVP but should reduce confidence.",
        )
    else:
        passed = market_cap > 1_000_000_000
        add_filter_result(
            results,
            "market_cap_above_1b",
            passed,
            f"Market cap is {market_cap:,.0f}.",
        )

    # Positive earnings filter
    earnings_value = eps_ttm if eps_ttm is not None else earnings_share

    if earnings_value is None:
        add_filter_result(
            results,
            "positive_earnings",
            False,
            "EPS/earnings field is missing.",
        )
    else:
        passed = earnings_value > 0
        add_filter_result(
            results,
            "positive_earnings",
            passed,
            f"Earnings value is {earnings_value}.",
        )

    # Positive operating margin filter
    if operating_margin is None:
        add_filter_result(
            results,
            "positive_operating_margin",
            False,
            "Operating margin is missing.",
        )
    else:
        passed = operating_margin > 0
        add_filter_result(
            results,
            "positive_operating_margin",
            passed,
            f"Operating margin is {operating_margin}.",
        )

    # Debt/equity filter
    if financial_sector:
        add_filter_result(
            results,
            "debt_equity_below_1_5",
            True,
            "Debt/equity filter skipped because company appears to be in the financial sector.",
        )
    elif debt_equity is None:
        add_filter_result(
            results,
            "debt_equity_below_1_5",
            True,
            "Debt/equity is missing; allowed for MVP but should reduce confidence.",
        )
    else:
        passed = debt_equity < 1.5
        add_filter_result(
            results,
            "debt_equity_below_1_5",
            passed,
            f"Debt/equity is {debt_equity}.",
        )

    # P/E filter
    if pe_ttm is None:
        add_filter_result(
            results,
            "pe_between_0_and_50",
            False,
            "Trailing P/E is missing.",
        )
    else:
        passed = 0 < pe_ttm < 50
        add_filter_result(
            results,
            "pe_between_0_and_50",
            passed,
            f"Trailing P/E is {pe_ttm}.",
        )

    overall_pass = all(result["passed"] for result in results)

    return {
        "passed": overall_pass,
        "is_financial_sector": financial_sector,
        "results": results,
    }