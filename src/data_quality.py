"""
Data-quality checks for normalized EODHD fundamentals.

MVP purpose:
- Identify missing, stale, or suspicious fields.
- Produce structured flags that can later feed scoring, filtering, and reports.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


REQUIRED_FIELDS = [
    "company_name",
    "security_type",
    "exchange",
    "currency",
    "sector",
    "industry",
    "market_cap",
    "pe_ttm",
    "operating_margin_ttm",
    "eps_ttm",
]

OPTIONAL_FIELDS = [
    "forward_pe",
    "price_sales_ttm",
    "price_book_mrq",
    "peg_ratio",
    "roe_ttm",
    "roa_ttm",
    "quarterly_revenue_growth_yoy",
    "quarterly_earnings_growth_yoy",
    "shares_outstanding",
    "forward_annual_dividend_yield",
    "payout_ratio",
]

STALE_DATE_FIELDS = {
    "updated_at": 365,
    "most_recent_quarter": 180,
}


def parse_date(value: Any) -> date | None:
    """Parse a date-like EODHD value into a Python date."""
    if value is None:
        return None

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt).date()
        except ValueError:
            continue

    return None


def add_flag(
    flags: list[dict[str, Any]],
    ticker: str,
    field: str,
    issue_type: str,
    severity: str,
    explanation: str,
    recommended_action: str,
) -> None:
    """Append a structured data-quality flag."""
    flags.append(
        {
            "ticker": ticker,
            "field": field,
            "issue_type": issue_type,
            "severity": severity,
            "explanation": explanation,
            "recommended_action": recommended_action,
        }
    )


def check_missing_fields(ticker: str, values: dict[str, Any]) -> list[dict[str, Any]]:
    """Flag missing required and optional fields."""
    flags: list[dict[str, Any]] = []

    for field in REQUIRED_FIELDS:
        if values.get(field) is None:
            add_flag(
                flags,
                ticker,
                field,
                "missing_required",
                "high",
                f"Required field '{field}' is missing.",
                "Do not use this company in the main ranked screener until the field is available or a fallback is implemented.",
            )

    for field in OPTIONAL_FIELDS:
        if values.get(field) is None:
            add_flag(
                flags,
                ticker,
                field,
                "missing_optional",
                "low",
                f"Optional field '{field}' is missing.",
                "Allow scoring to continue, but reduce confidence if many optional fields are missing.",
            )

    return flags


def check_stale_dates(
    ticker: str,
    values: dict[str, Any],
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """Flag stale date fields."""
    flags: list[dict[str, Any]] = []
    as_of = as_of or date.today()

    for field, max_age_days in STALE_DATE_FIELDS.items():
        parsed = parse_date(values.get(field))

        if parsed is None:
            add_flag(
                flags,
                ticker,
                field,
                "missing_date",
                "medium",
                f"Date field '{field}' is missing or could not be parsed.",
                "Keep the company, but mark freshness as uncertain.",
            )
            continue

        age_days = (as_of - parsed).days

        if age_days > max_age_days:
            add_flag(
                flags,
                ticker,
                field,
                "stale_field",
                "medium",
                f"Field '{field}' is {age_days} days old, exceeding the {max_age_days}-day threshold.",
                "Refresh data or reduce confidence before ranking.",
            )

    return flags


def check_suspicious_ratios(ticker: str, values: dict[str, Any]) -> list[dict[str, Any]]:
    """Flag negative or nonsensical valuation/profitability ratios."""
    flags: list[dict[str, Any]] = []

    pe = values.get("pe_ttm")
    if pe is not None:
        if pe <= 0:
            add_flag(
                flags,
                ticker,
                "pe_ttm",
                "negative_or_zero_pe",
                "high",
                "Trailing P/E is less than or equal to zero.",
                "Do not treat this as a cheap stock. It should fail positive earnings or P/E filters.",
            )
        elif pe > 100:
            add_flag(
                flags,
                ticker,
                "pe_ttm",
                "extreme_pe",
                "medium",
                "Trailing P/E is above 100.",
                "Check whether EPS is stale, very small, or inconsistent with price.",
            )

    forward_pe = values.get("forward_pe")
    if forward_pe is not None and forward_pe <= 0:
        add_flag(
            flags,
            ticker,
            "forward_pe",
            "negative_or_zero_forward_pe",
            "medium",
            "Forward P/E is less than or equal to zero.",
            "Exclude forward P/E from scoring unless validated.",
        )

    pb = values.get("price_book_mrq")
    if pb is not None and pb < 0:
        add_flag(
            flags,
            ticker,
            "price_book_mrq",
            "negative_price_book",
            "medium",
            "Price/book is negative.",
            "Validate book value and equity before using this ratio.",
        )

    ps = values.get("price_sales_ttm")
    if ps is not None and ps < 0:
        add_flag(
            flags,
            ticker,
            "price_sales_ttm",
            "negative_price_sales",
            "medium",
            "Price/sales is negative.",
            "Validate revenue and market cap before using this ratio.",
        )

    operating_margin = values.get("operating_margin_ttm")
    if operating_margin is not None:
        if operating_margin < -1 or operating_margin > 1:
            add_flag(
                flags,
                ticker,
                "operating_margin_ttm",
                "suspicious_margin",
                "medium",
                "Operating margin is outside the expected -100% to 100% range.",
                "Validate margin scale before using this field.",
            )

    return flags


def run_data_quality_checks(
    ticker: str,
    values: dict[str, Any],
    as_of: date | None = None,
) -> list[dict[str, Any]]:
    """Run all MVP data-quality checks."""
    flags: list[dict[str, Any]] = []

    flags.extend(check_missing_fields(ticker, values))
    flags.extend(check_stale_dates(ticker, values, as_of=as_of))
    flags.extend(check_suspicious_ratios(ticker, values))

    return flags