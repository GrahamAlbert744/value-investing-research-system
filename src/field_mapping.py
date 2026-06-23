"""
Field mapping utilities for EODHD fundamentals data.

MVP purpose:
- Convert raw EODHD section payloads into normalized field names.
- Keep source fields traceable.
- Handle missing values gracefully.
- Prepare normalized values for scoring, filtering, and data-quality checks.

This module reads raw JSON files saved by scripts/run_single_ticker.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RAW_DIR = Path("data/raw")


# Map project-standard field names to EODHD source section and source field.
#
# Format:
#     "normalized_field": ("EODHD section", "EODHD field")
#
# These mappings are intentionally conservative for the MVP.
# We will refine them after inspecting more EODHD responses.
FIELD_SOURCES: dict[str, tuple[str, str]] = {
    # ------------------------------------------------------------------
    # Company identity
    # ------------------------------------------------------------------
    "company_name": ("General", "Name"),
    "ticker_code": ("General", "Code"),
    "security_type": ("General", "Type"),
    "exchange": ("General", "Exchange"),
    "currency": ("General", "CurrencyCode"),
    "country": ("General", "CountryName"),
    "country_iso": ("General", "CountryISO"),
    "sector": ("General", "Sector"),
    "industry": ("General", "Industry"),
    "isin": ("General", "ISIN"),
    "primary_ticker": ("General", "PrimaryTicker"),
    "is_delisted": ("General", "IsDelisted"),
    "updated_at": ("General", "UpdatedAt"),

    # ------------------------------------------------------------------
    # Value / valuation
    # ------------------------------------------------------------------
    "market_cap": ("Highlights", "MarketCapitalization"),
    "market_cap_mln": ("Highlights", "MarketCapitalizationMln"),
    "pe_ttm": ("Valuation", "TrailingPE"),
    "forward_pe": ("Valuation", "ForwardPE"),
    "price_sales_ttm": ("Valuation", "PriceSalesTTM"),
    "price_book_mrq": ("Valuation", "PriceBookMRQ"),
    "enterprise_value": ("Valuation", "EnterpriseValue"),
    "enterprise_value_revenue": ("Valuation", "EnterpriseValueRevenue"),
    "enterprise_value_ebitda": ("Valuation", "EnterpriseValueEbitda"),
    "peg_ratio": ("Highlights", "PEGRatio"),

    # ------------------------------------------------------------------
    # Profitability / quality
    # ------------------------------------------------------------------
    "operating_margin_ttm": ("Highlights", "OperatingMarginTTM"),
    "net_margin": ("Highlights", "ProfitMargin"),
    "roa_ttm": ("Highlights", "ReturnOnAssetsTTM"),
    "roe_ttm": ("Highlights", "ReturnOnEquityTTM"),
    "gross_profit_ttm": ("Highlights", "GrossProfitTTM"),
    "ebitda": ("Highlights", "EBITDA"),

    # ------------------------------------------------------------------
    # Earnings / growth
    # ------------------------------------------------------------------
    "eps_ttm": ("Highlights", "DilutedEpsTTM"),
    "earnings_share": ("Highlights", "EarningsShare"),
    "eps_estimate_current_year": ("Highlights", "EPSEstimateCurrentYear"),
    "eps_estimate_next_year": ("Highlights", "EPSEstimateNextYear"),
    "revenue_ttm": ("Highlights", "RevenueTTM"),
    "revenue_per_share_ttm": ("Highlights", "RevenuePerShareTTM"),
    "quarterly_revenue_growth_yoy": ("Highlights", "QuarterlyRevenueGrowthYOY"),
    "quarterly_earnings_growth_yoy": ("Highlights", "QuarterlyEarningsGrowthYOY"),
    "most_recent_quarter": ("Highlights", "MostRecentQuarter"),

    # ------------------------------------------------------------------
    # Shares
    # ------------------------------------------------------------------
    "shares_outstanding": ("SharesStats", "SharesOutstanding"),
    "shares_float": ("SharesStats", "SharesFloat"),
    "percent_insiders": ("SharesStats", "PercentInsiders"),
    "percent_institutions": ("SharesStats", "PercentInstitutions"),
    "shares_short": ("SharesStats", "SharesShort"),
    "short_percent_float": ("SharesStats", "ShortPercentFloat"),

    # ------------------------------------------------------------------
    # Dividends / splits
    # ------------------------------------------------------------------
    "forward_annual_dividend_rate": (
        "SplitsDividends",
        "ForwardAnnualDividendRate",
    ),
    "forward_annual_dividend_yield": (
        "SplitsDividends",
        "ForwardAnnualDividendYield",
    ),
    "payout_ratio": ("SplitsDividends", "PayoutRatio"),
    "dividend_date": ("SplitsDividends", "DividendDate"),
    "ex_dividend_date": ("SplitsDividends", "ExDividendDate"),
    "last_split_factor": ("SplitsDividends", "LastSplitFactor"),
    "last_split_date": ("SplitsDividends", "LastSplitDate"),
}


def load_raw_section(
    ticker: str,
    section: str,
    raw_dir: Path = RAW_DIR,
) -> dict[str, Any]:
    """
    Load a saved raw EODHD JSON section.

    Parameters
    ----------
    ticker:
        EODHD ticker, for example "AAPL.US".
    section:
        EODHD fundamentals section, for example "General".
    raw_dir:
        Directory containing saved raw JSON files.

    Returns
    -------
    dict
        Parsed JSON dictionary. Returns an empty dictionary if the file
        does not exist or if the response is not a dictionary.
    """
    path = raw_dir / f"{ticker}_{section}.json"

    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def normalize_ticker_fields(
    ticker: str,
    raw_dir: Path = RAW_DIR,
) -> dict[str, dict[str, Any]]:
    """
    Normalize selected raw EODHD fields into project-standard field names.

    Returns
    -------
    dict
        A dictionary where each normalized field contains metadata:

        {
            "normalized_field": {
                "value": ...,
                "source_section": ...,
                "source_field": ...,
                "is_missing": ...,
                "source_file": ...
            }
        }

    Notes
    -----
    This function does not calculate ratios yet.
    It only maps directly available EODHD fields.
    """
    normalized: dict[str, dict[str, Any]] = {}

    # Cache each section so we only read each JSON file once.
    section_cache: dict[str, dict[str, Any]] = {}

    for normalized_field, (section, source_field) in FIELD_SOURCES.items():
        if section not in section_cache:
            section_cache[section] = load_raw_section(ticker, section, raw_dir)

        section_data = section_cache[section]
        value = section_data.get(source_field)

        normalized[normalized_field] = {
            "value": value,
            "source_section": section,
            "source_field": source_field,
            "is_missing": value is None,
            "source_file": str(raw_dir / f"{ticker}_{section}.json"),
        }

    return normalized


def flatten_normalized_fields(
    normalized: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Flatten normalized field metadata into simple field-value pairs.

    Parameters
    ----------
    normalized:
        Output from normalize_ticker_fields.

    Returns
    -------
    dict
        Simple dictionary of normalized field names to values.

    Example
    -------
    {
        "company_name": "Apple Inc",
        "market_cap": 3000000000000,
        "pe_ttm": 30.5
    }
    """
    return {field: meta.get("value") for field, meta in normalized.items()}


def normalized_fields_to_rows(
    ticker: str,
    normalized: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert normalized field metadata into rows for CSV export.

    Parameters
    ----------
    ticker:
        EODHD ticker.
    normalized:
        Output from normalize_ticker_fields.

    Returns
    -------
    list[dict]
        Row-oriented representation suitable for pandas DataFrame.
    """
    rows: list[dict[str, Any]] = []

    for normalized_field, meta in normalized.items():
        rows.append(
            {
                "ticker": ticker,
                "normalized_field": normalized_field,
                "value": meta.get("value"),
                "source_section": meta.get("source_section"),
                "source_field": meta.get("source_field"),
                "is_missing": meta.get("is_missing"),
                "source_file": meta.get("source_file"),
            }
        )

    return rows