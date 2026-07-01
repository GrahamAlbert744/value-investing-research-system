"""
Revise config/field_mapping.yml to support fallback raw_paths.

Inputs:
- outputs/eodhd_field_audit.csv
- existing config/field_mapping.yml, if present

Output:
- config/field_mapping.yml

This script only maps candidate raw paths that actually appear in the
field audit CSV. Missing candidates are tracked under missing_fields.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIELD_AUDIT_PATH = PROJECT_ROOT / "outputs" / "eodhd_field_audit.csv"
FIELD_MAPPING_PATH = PROJECT_ROOT / "config" / "field_mapping.yml"


CANDIDATE_MAPPINGS: dict[str, dict[str, Any]] = {
    # Identity and metadata
    "code": {
        "candidate_paths": ["General.Code"],
        "category": "identity",
        "required": True,
        "description": "Ticker code without exchange suffix.",
    },
    "primary_ticker": {
        "candidate_paths": ["General.PrimaryTicker"],
        "category": "identity",
        "required": False,
        "description": "Primary ticker if provided by EODHD.",
    },
    "ticker": {
        "candidate_paths": ["General.PrimaryTicker", "General.Code"],
        "category": "identity",
        "required": True,
        "description": "Best available ticker identifier from fundamentals.",
    },
    "name": {
        "candidate_paths": ["General.Name"],
        "category": "identity",
        "required": True,
        "description": "Company name.",
    },
    "company_name": {
        "candidate_paths": ["General.Name"],
        "category": "identity",
        "required": True,
        "description": "Company name duplicate for downstream compatibility.",
    },
    "exchange": {
        "candidate_paths": ["General.Exchange"],
        "category": "identity",
        "required": True,
        "description": "Exchange code or EODHD exchange identifier.",
    },
    "security_type": {
        "candidate_paths": ["General.Type"],
        "category": "identity",
        "required": True,
        "description": "Security type such as Common Stock, ETF, Fund, etc.",
    },
    "type": {
        "candidate_paths": ["General.Type"],
        "category": "identity",
        "required": False,
        "description": "Backward-compatible alias for security_type.",
    },
    "country": {
        "candidate_paths": ["General.CountryName", "General.CountryISO"],
        "category": "identity",
        "required": False,
        "description": "Company country.",
    },
    "country_iso": {
        "candidate_paths": ["General.CountryISO"],
        "category": "identity",
        "required": False,
        "description": "Company country ISO code.",
    },
    "currency": {
        "candidate_paths": ["General.CurrencyCode", "General.CurrencyName"],
        "category": "metadata",
        "required": True,
        "description": "Reported currency.",
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
    "is_delisted": {
        "candidate_paths": ["General.IsDelisted"],
        "category": "identity",
        "required": False,
        "description": "Whether the security is delisted, if provided.",
    },
    "isin": {
        "candidate_paths": ["General.ISIN"],
        "category": "identity",
        "required": False,
        "description": "ISIN identifier.",
    },
    "open_figi": {
        "candidate_paths": ["General.OpenFigi"],
        "category": "identity",
        "required": False,
        "description": "OpenFIGI identifier.",
    },
    "cik": {
        "candidate_paths": ["General.CIK"],
        "category": "identity",
        "required": False,
        "description": "SEC CIK identifier when available.",
    },
    "lei": {
        "candidate_paths": ["General.LEI"],
        "category": "identity",
        "required": False,
        "description": "Legal Entity Identifier when available.",
    },
    "fiscal_year_end": {
        "candidate_paths": ["General.FiscalYearEnd"],
        "category": "metadata",
        "required": False,
        "description": "Fiscal year end.",
    },
    "ipo_date": {
        "candidate_paths": ["General.IPODate"],
        "category": "metadata",
        "required": False,
        "description": "IPO date.",
    },
    "fundamentals_updated_at": {
        "candidate_paths": ["General.UpdatedAt"],
        "category": "metadata",
        "required": False,
        "description": "EODHD fundamentals update timestamp.",
    },

    # Summary valuation and profitability
    "market_capitalization": {
        "candidate_paths": ["Highlights.MarketCapitalization"],
        "category": "valuation",
        "required": True,
        "description": "Market capitalization.",
    },
    "enterprise_value": {
        "candidate_paths": ["Valuation.EnterpriseValue"],
        "category": "valuation",
        "required": False,
        "description": "Enterprise value.",
    },
    "ebitda": {
        "candidate_paths": ["Highlights.EBITDA"],
        "category": "quality",
        "required": False,
        "description": "EBITDA.",
    },
    "pe_ratio": {
        "candidate_paths": ["Highlights.PERatio", "Valuation.TrailingPE"],
        "category": "valuation",
        "required": False,
        "description": "Price-to-earnings ratio.",
    },
    "trailing_pe": {
        "candidate_paths": ["Valuation.TrailingPE", "Highlights.PERatio"],
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
    "peg_ratio": {
        "candidate_paths": ["Highlights.PEGRatio"],
        "category": "valuation",
        "required": False,
        "description": "PEG ratio.",
    },
    "book_value": {
        "candidate_paths": ["Highlights.BookValue"],
        "category": "valuation",
        "required": False,
        "description": "Book value metric.",
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

    # Dividends
    "dividend_yield": {
        "candidate_paths": [
            "SplitsDividends.ForwardAnnualDividendYield",
            "Highlights.DividendYield",
        ],
        "category": "dividends",
        "required": False,
        "description": "Dividend yield. Prefer explicit forward annual dividend yield if available.",
    },
    "payout_ratio": {
        "candidate_paths": ["SplitsDividends.PayoutRatio"],
        "category": "dividends",
        "required": False,
        "description": "Dividend payout ratio.",
    },

    # Growth and profitability
    "eps": {
        "candidate_paths": ["Highlights.EarningsShare"],
        "category": "quality",
        "required": False,
        "description": "Earnings per share.",
    },
    "diluted_eps_ttm": {
        "candidate_paths": ["Highlights.DilutedEpsTTM"],
        "category": "quality",
        "required": False,
        "description": "Diluted EPS TTM.",
    },
    "revenue_ttm": {
        "candidate_paths": ["Highlights.RevenueTTM"],
        "category": "quality",
        "required": False,
        "description": "Revenue TTM.",
    },
    "gross_profit_ttm": {
        "candidate_paths": ["Highlights.GrossProfitTTM"],
        "category": "quality",
        "required": False,
        "description": "Gross profit TTM.",
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
        "description": "Operating margin TTM.",
    },
    "return_on_assets_ttm": {
        "candidate_paths": ["Highlights.ReturnOnAssetsTTM"],
        "category": "quality",
        "required": False,
        "description": "Return on assets TTM.",
    },
    "return_on_equity_ttm": {
        "candidate_paths": ["Highlights.ReturnOnEquityTTM"],
        "category": "quality",
        "required": False,
        "description": "Return on equity TTM.",
    },
    "quarterly_revenue_growth_yoy": {
        "candidate_paths": ["Highlights.QuarterlyRevenueGrowthYOY"],
        "category": "growth",
        "required": False,
        "description": "Quarterly revenue growth YoY.",
    },
    "quarterly_earnings_growth_yoy": {
        "candidate_paths": ["Highlights.QuarterlyEarningsGrowthYOY"],
        "category": "growth",
        "required": False,
        "description": "Quarterly earnings growth YoY.",
    },
    "most_recent_quarter": {
        "candidate_paths": ["Highlights.MostRecentQuarter"],
        "category": "metadata",
        "required": False,
        "description": "Most recent reported quarter.",
    },

    # Shares and market data
    "shares_outstanding": {
        "candidate_paths": [
            "SharesStats.SharesOutstanding",
            "SharesStats.SharesOutstandingMln",
        ],
        "category": "shares",
        "required": False,
        "description": "Shares outstanding.",
    },
    "shares_float": {
        "candidate_paths": ["SharesStats.SharesFloat"],
        "category": "shares",
        "required": False,
        "description": "Public float shares.",
    },
    "beta": {
        "candidate_paths": ["Technicals.Beta"],
        "category": "stability",
        "required": False,
        "description": "Beta.",
    },
}


def load_existing_mapping(path: Path) -> dict[str, Any]:
    """Load existing mapping if present."""
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        mapping = yaml.safe_load(file)

    if not isinstance(mapping, dict):
        return {}

    return mapping


def choose_existing_paths(existing_spec: dict[str, Any]) -> list[str]:
    """Extract existing raw path(s) from older mapping style."""
    if not isinstance(existing_spec, dict):
        return []

    raw_paths = existing_spec.get("raw_paths")
    if isinstance(raw_paths, list):
        return [str(path) for path in raw_paths if path]

    raw_path = existing_spec.get("raw_path")
    if raw_path:
        return [str(raw_path)]

    return []


def main() -> None:
    if not FIELD_AUDIT_PATH.exists():
        raise FileNotFoundError(
            f"Missing field audit file: {FIELD_AUDIT_PATH}\n"
            "Run scripts\\build_eodhd_field_audit.py first."
        )

    audit_df = pd.read_csv(FIELD_AUDIT_PATH)

    if "path" not in audit_df.columns:
        raise ValueError("Field audit CSV must contain a 'path' column.")

    available_paths = set(audit_df["path"].dropna().astype(str).tolist())
    existing_mapping = load_existing_mapping(FIELD_MAPPING_PATH)
    existing_fields = existing_mapping.get("mapped_fields", {})

    mapped_fields: dict[str, Any] = {}
    missing_fields: dict[str, Any] = {}

    for normalized_name, spec in CANDIDATE_MAPPINGS.items():
        candidate_paths = spec["candidate_paths"]

        existing_paths = choose_existing_paths(existing_fields.get(normalized_name, {}))

        combined_candidates = []
        for path in candidate_paths + existing_paths:
            if path not in combined_candidates:
                combined_candidates.append(path)

        matched_paths = [path for path in combined_candidates if path in available_paths]

        if matched_paths:
            mapped_fields[normalized_name] = {
                "raw_paths": matched_paths,
                "raw_path": matched_paths[0],
                "category": spec["category"],
                "required": spec["required"],
                "description": spec["description"],
            }
        else:
            missing_fields[normalized_name] = {
                "candidate_paths": combined_candidates,
                "category": spec["category"],
                "required": spec["required"],
                "description": spec["description"],
            }

    output = {
        "metadata": {
            "purpose": "Fallback-aware mapping from normalized field names to EODHD raw fundamentals paths.",
            "source_file": str(FIELD_AUDIT_PATH.relative_to(PROJECT_ROOT)),
            "notes": [
                "raw_paths is the ordered fallback list.",
                "raw_path is retained for backward compatibility.",
                "Only paths found in outputs/eodhd_field_audit.csv are mapped.",
            ],
        },
        "mapped_fields": mapped_fields,
        "missing_fields": missing_fields,
    }

    with FIELD_MAPPING_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(output, file, sort_keys=False)

    print(f"Updated field mapping saved to: {FIELD_MAPPING_PATH}")
    print(f"Mapped fields: {len(mapped_fields)}")
    print(f"Missing fields: {len(missing_fields)}")

    if missing_fields:
        print("\nMissing normalized fields:")
        for field_name, field_spec in missing_fields.items():
            required_label = "required" if field_spec.get("required") else "optional"
            print(f"- {field_name} ({required_label})")


if __name__ == "__main__":
    main()