"""
Apply semantic cleanup corrections to config/field_mapping.yml after EODHD C2 review.

This script:
- removes mixed-type fallback paths
- separates current dividend yield from forward dividend yield
- adds currency_name and currency_symbol when available
- documents derived valuation/scoring fields that come from statements, not direct raw paths
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIELD_AUDIT_PATH = PROJECT_ROOT / "outputs" / "eodhd_field_audit.csv"
FIELD_MAPPING_PATH = PROJECT_ROOT / "config" / "field_mapping.yml"


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise TypeError(f"Expected dictionary YAML from {path}")

    return data


def path_exists(path: str, available_paths: set[str]) -> bool:
    return path in available_paths


def set_mapping(
    mapped_fields: dict[str, Any],
    field_name: str,
    raw_paths: list[str],
    category: str,
    required: bool,
    description: str,
) -> None:
    mapped_fields[field_name] = {
        "raw_paths": raw_paths,
        "raw_path": raw_paths[0] if raw_paths else None,
        "category": category,
        "required": required,
        "description": description,
    }


def add_if_available(
    mapped_fields: dict[str, Any],
    available_paths: set[str],
    field_name: str,
    candidate_paths: list[str],
    category: str,
    required: bool,
    description: str,
) -> None:
    matched_paths = [path for path in candidate_paths if path_exists(path, available_paths)]

    if matched_paths:
        set_mapping(
            mapped_fields=mapped_fields,
            field_name=field_name,
            raw_paths=matched_paths,
            category=category,
            required=required,
            description=description,
        )


def main() -> None:
    if not FIELD_AUDIT_PATH.exists():
        raise FileNotFoundError(
            f"Missing field audit file: {FIELD_AUDIT_PATH}\n"
            "Run scripts\\build_eodhd_field_audit.py first."
        )

    mapping = load_yaml(FIELD_MAPPING_PATH)
    mapped_fields = mapping.get("mapped_fields", {})

    if not isinstance(mapped_fields, dict):
        raise TypeError("field_mapping.yml must contain mapped_fields dictionary.")

    audit_df = pd.read_csv(FIELD_AUDIT_PATH)
    available_paths = set(audit_df["path"].dropna().astype(str).tolist())

    # 1. Avoid suffix/no-suffix semantic mixing.
    set_mapping(
        mapped_fields=mapped_fields,
        field_name="ticker",
        raw_paths=["General.PrimaryTicker"],
        category="identity",
        required=True,
        description=(
            "Primary ticker with exchange suffix from General.PrimaryTicker. "
            "If missing, use source_symbol outside raw path mapping; do not silently "
            "fallback to suffix-less General.Code."
        ),
    )

    # 2. Avoid country name/code mixing.
    set_mapping(
        mapped_fields=mapped_fields,
        field_name="country",
        raw_paths=["General.CountryName"],
        category="identity",
        required=False,
        description="Company country name from General.CountryName.",
    )

    # 3. Avoid currency code/name mixing.
    set_mapping(
        mapped_fields=mapped_fields,
        field_name="currency",
        raw_paths=["General.CurrencyCode"],
        category="metadata",
        required=True,
        description=(
            "Security currency code from General.CurrencyCode. Do not assume this is "
            "the financial-statement reporting currency without verification."
        ),
    )

    # 4. Add separate currency display fields.
    add_if_available(
        mapped_fields=mapped_fields,
        available_paths=available_paths,
        field_name="currency_name",
        candidate_paths=["General.CurrencyName"],
        category="metadata",
        required=False,
        description="Currency display name from General.CurrencyName.",
    )

    add_if_available(
        mapped_fields=mapped_fields,
        available_paths=available_paths,
        field_name="currency_symbol",
        candidate_paths=["General.CurrencySymbol"],
        category="metadata",
        required=False,
        description="Currency symbol from General.CurrencySymbol.",
    )

    # 5. Make dividend_yield prefer Highlights.DividendYield.
    available_dividend_paths = [
        path
        for path in [
            "Highlights.DividendYield",
            "SplitsDividends.ForwardAnnualDividendYield",
        ]
        if path_exists(path, available_paths)
    ]

    if available_dividend_paths:
        set_mapping(
            mapped_fields=mapped_fields,
            field_name="dividend_yield",
            raw_paths=available_dividend_paths,
            category="dividends",
            required=False,
            description=(
                "Dividend yield. Prefer Highlights.DividendYield; fallback to "
                "forward annual dividend yield only if current dividend yield is unavailable."
            ),
        )

    # 6. Add forward dividend yield as a separate semantic field.
    add_if_available(
        mapped_fields=mapped_fields,
        available_paths=available_paths,
        field_name="forward_annual_dividend_yield",
        candidate_paths=["SplitsDividends.ForwardAnnualDividendYield"],
        category="dividends",
        required=False,
        description="Forward annual dividend yield from SplitsDividends.ForwardAnnualDividendYield.",
    )

    # 7. Clarify descriptions for ambiguous-but-valid fields.
    if "exchange" in mapped_fields:
        mapped_fields["exchange"]["description"] = (
            "Exchange value from EODHD General.Exchange. May be display exchange/name/code "
            "rather than the API ticker suffix."
        )

    if "book_value" in mapped_fields:
        mapped_fields["book_value"]["description"] = (
            "Book value field from EODHD Highlights.BookValue. Exact unit/definition "
            "should be verified before using in valuation calculations."
        )

    if "pe_ratio" in mapped_fields:
        mapped_fields["pe_ratio"]["description"] = (
            "Backward-compatible PE alias. Prefer trailing_pe as the canonical scoring field."
        )

    # 8. Mark key freshness fields as required before production scoring.
    for field_name in [
        "is_delisted",
        "fundamentals_updated_at",
        "most_recent_quarter",
        "sector",
        "industry",
    ]:
        if field_name in mapped_fields:
            mapped_fields[field_name]["required"] = True

    # 9. Add documentation for derived fields needed later.
    mapping["derived_fields_needed"] = {
        "latest_revenue": {
            "reason": "Needed for sales-multiple valuation and sanity checks.",
            "source": "computed_from_financial_statements",
            "status": "handled_in_financial_statement_summary_or_C5",
        },
        "latest_net_income": {
            "reason": "Needed for earnings-power valuation.",
            "source": "computed_from_financial_statements",
            "status": "handled_in_financial_statement_summary_or_C5",
        },
        "latest_free_cash_flow": {
            "reason": "Needed for FCF valuation.",
            "source": "computed_from_financial_statements",
            "status": "handled_in_financial_statement_summary_or_C5",
        },
        "latest_net_margin": {
            "reason": "Needed to reject weak sales-multiple valuations.",
            "source": "computed_from latest_net_income / latest_revenue",
            "status": "handled_in_financial_statement_summary_or_C5",
        },
        "latest_fcf_margin": {
            "reason": "Needed to assess cash conversion.",
            "source": "computed_from latest_free_cash_flow / latest_revenue",
            "status": "handled_in_financial_statement_summary_or_C5",
        },
        "latest_liabilities_to_assets": {
            "reason": "Needed for balance-sheet risk filtering.",
            "source": "computed_from total liabilities / total assets",
            "status": "handled_in_financial_statement_summary_or_C5",
        },
        "required_fields_missing": {
            "reason": "Needed for scoring and research queue data-quality flags.",
            "source": "computed_by_data_quality_layer",
            "status": "planned_for_C3",
        },
        "stale_data_flag": {
            "reason": "Needed to prevent stale fundamentals from receiving normal scores.",
            "source": "computed_by_data_quality_layer",
            "status": "planned_for_C3",
        },
    }

    mapping["mapped_fields"] = mapped_fields

    with FIELD_MAPPING_PATH.open("w", encoding="utf-8") as file:
        yaml.safe_dump(mapping, file, sort_keys=False)

    print(f"Applied C2 semantic corrections to: {FIELD_MAPPING_PATH}")
    print(f"Mapped fields now: {len(mapped_fields)}")
    print("Key corrections applied:")
    print("- ticker no longer falls back to General.Code")
    print("- country no longer falls back to General.CountryISO")
    print("- currency no longer falls back to General.CurrencyName")
    print("- dividend_yield and forward_annual_dividend_yield separated")
    print("- derived_fields_needed section added")


if __name__ == "__main__":
    main()