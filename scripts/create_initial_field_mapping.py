"""
Create an initial config/field_mapping.yml from outputs/eodhd_field_audit.csv.

This script does not assume every EODHD field exists.
It checks the actual field audit CSV and only maps fields whose raw paths exist.

Output:
- config/field_mapping.yml
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIELD_AUDIT_PATH = PROJECT_ROOT / "outputs" / "eodhd_field_audit.csv"
OUTPUT_PATH = PROJECT_ROOT / "config" / "field_mapping.yml"


CANDIDATE_MAPPINGS = {
    "ticker": {
        "candidate_paths": ["General.Code"],
        "category": "identity",
        "required": True,
        "description": "Ticker symbol without exchange suffix if provided by EODHD.",
    },
    "exchange": {
        "candidate_paths": ["General.Exchange"],
        "category": "identity",
        "required": True,
        "description": "Exchange code or exchange name.",
    },
    "name": {
        "candidate_paths": ["General.Name"],
        "category": "identity",
        "required": True,
        "description": "Company name.",
    },
    "type": {
        "candidate_paths": ["General.Type"],
        "category": "identity",
        "required": False,
        "description": "Security type, such as Common Stock or ETF.",
    },
    "sector": {
        "candidate_paths": ["General.Sector"],
        "category": "identity",
        "required": True,
        "description": "Company sector.",
    },
    "industry": {
        "candidate_paths": ["General.Industry"],
        "category": "identity",
        "required": True,
        "description": "Company industry.",
    },
    "country": {
        "candidate_paths": ["General.CountryName", "General.CountryISO"],
        "category": "identity",
        "required": False,
        "description": "Company country.",
    },
    "currency": {
        "candidate_paths": ["General.CurrencyCode", "General.CurrencyName"],
        "category": "metadata",
        "required": True,
        "description": "Reported currency.",
    },
    "market_capitalization": {
        "candidate_paths": ["Highlights.MarketCapitalization"],
        "category": "valuation",
        "required": True,
        "description": "Market capitalization.",
    },
    "ebitda": {
        "candidate_paths": ["Highlights.EBITDA"],
        "category": "quality",
        "required": False,
        "description": "EBITDA.",
    },
    "pe_ratio": {
        "candidate_paths": ["Highlights.PERatio"],
        "category": "valuation",
        "required": False,
        "description": "Price-to-earnings ratio.",
    },
    "peg_ratio": {
        "candidate_paths": ["Highlights.PEGRatio"],
        "category": "valuation",
        "required": False,
        "description": "Price/earnings-to-growth ratio.",
    },
    "book_value": {
        "candidate_paths": ["Highlights.BookValue"],
        "category": "valuation",
        "required": False,
        "description": "Book value per share or reported book value metric.",
    },
    "dividend_yield": {
        "candidate_paths": ["Highlights.DividendYield"],
        "category": "dividends",
        "required": False,
        "description": "Dividend yield.",
    },
    "eps": {
        "candidate_paths": ["Highlights.EarningsShare"],
        "category": "quality",
        "required": False,
        "description": "Earnings per share.",
    },
    "revenue_ttm": {
        "candidate_paths": ["Highlights.RevenueTTM"],
        "category": "quality",
        "required": False,
        "description": "Trailing twelve-month revenue.",
    },
    "gross_profit_ttm": {
        "candidate_paths": ["Highlights.GrossProfitTTM"],
        "category": "quality",
        "required": False,
        "description": "Trailing twelve-month gross profit.",
    },
    "diluted_eps_ttm": {
        "candidate_paths": ["Highlights.DilutedEpsTTM"],
        "category": "quality",
        "required": False,
        "description": "Trailing twelve-month diluted EPS.",
    },
    "quarterly_revenue_growth_yoy": {
        "candidate_paths": ["Highlights.QuarterlyRevenueGrowthYOY"],
        "category": "growth",
        "required": False,
        "description": "Year-over-year quarterly revenue growth.",
    },
    "quarterly_earnings_growth_yoy": {
        "candidate_paths": ["Highlights.QuarterlyEarningsGrowthYOY"],
        "category": "growth",
        "required": False,
        "description": "Year-over-year quarterly earnings growth.",
    },
    "profit_margin": {
        "candidate_paths": ["Highlights.ProfitMargin"],
        "category": "quality",
        "required": False,
        "description": "Profit margin.",
    },
    "operating_margin_ttm": {
        "candidate_paths": ["Highlights.OperatingMarginTTM"],
        "category": "quality",
        "required": False,
        "description": "Trailing twelve-month operating margin.",
    },
    "return_on_assets_ttm": {
        "candidate_paths": ["Highlights.ReturnOnAssetsTTM"],
        "category": "quality",
        "required": False,
        "description": "Trailing twelve-month return on assets.",
    },
    "return_on_equity_ttm": {
        "candidate_paths": ["Highlights.ReturnOnEquityTTM"],
        "category": "quality",
        "required": False,
        "description": "Trailing twelve-month return on equity.",
    },
    "trailing_pe": {
        "candidate_paths": ["Valuation.TrailingPE"],
        "category": "valuation",
        "required": False,
        "description": "Trailing price-to-earnings ratio.",
    },
    "forward_pe": {
        "candidate_paths": ["Valuation.ForwardPE"],
        "category": "valuation",
        "required": False,
        "description": "Forward price-to-earnings ratio.",
    },
    "price_sales_ttm": {
        "candidate_paths": ["Valuation.PriceSalesTTM"],
        "category": "valuation",
        "required": False,
        "description": "Price-to-sales ratio.",
    },
    "price_book_mrq": {
        "candidate_paths": ["Valuation.PriceBookMRQ"],
        "category": "valuation",
        "required": False,
        "description": "Price-to-book ratio.",
    },
    "enterprise_value": {
        "candidate_paths": ["Valuation.EnterpriseValue"],
        "category": "valuation",
        "required": False,
        "description": "Enterprise value.",
    },
    "enterprise_value_revenue": {
        "candidate_paths": ["Valuation.EnterpriseValueRevenue"],
        "category": "valuation",
        "required": False,
        "description": "Enterprise value to revenue.",
    },
    "enterprise_value_ebitda": {
        "candidate_paths": ["Valuation.EnterpriseValueEbitda"],
        "category": "valuation",
        "required": False,
        "description": "Enterprise value to EBITDA.",
    },
}


def find_first_existing_path(candidate_paths: list[str], available_paths: set[str]) -> str | None:
    """Return the first candidate path that exists in the field audit."""
    for path in candidate_paths:
        if path in available_paths:
            return path
    return None


def main() -> None:
    if not FIELD_AUDIT_PATH.exists():
        raise FileNotFoundError(
            f"Missing field audit: {FIELD_AUDIT_PATH}\n"
            "Run scripts\\build_eodhd_field_audit.py first."
        )

    audit_df = pd.read_csv(FIELD_AUDIT_PATH)
    available_paths = set(audit_df["path"].dropna().astype(str))

    mapped_fields = {}
    missing_fields = {}

    for normalized_name, spec in CANDIDATE_MAPPINGS.items():
        raw_path = find_first_existing_path(spec["candidate_paths"], available_paths)

        mapping_record = {
            "raw_path": raw_path,
            "candidate_paths_checked": spec["candidate_paths"],
            "category": spec["category"],
            "required": spec["required"],
            "description": spec["description"],
            "status": "mapped" if raw_path else "missing_from_audit",
        }

        if raw_path:
            mapped_fields[normalized_name] = mapping_record
        else:
            missing_fields[normalized_name] = mapping_record

    output = {
        "metadata": {
            "source": "EODHD fundamentals demo response",
            "field_audit_file": str(FIELD_AUDIT_PATH.relative_to(PROJECT_ROOT)),
            "notes": [
                "Generated from outputs/eodhd_field_audit.csv.",
                "Only paths found in the audit are marked as mapped.",
                "Missing fields should be reviewed before normalization.",
            ],
        },
        "mapped_fields": mapped_fields,
        "missing_fields": missing_fields,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(output, file, sort_keys=False, allow_unicode=True)

    print(f"Field mapping written to: {OUTPUT_PATH}")
    print(f"Mapped fields: {len(mapped_fields)}")
    print(f"Missing fields: {len(missing_fields)}")

    if missing_fields:
        print("\nMissing fields to review:")
        for field in missing_fields:
            print(f"- {field}")


if __name__ == "__main__":
    main()