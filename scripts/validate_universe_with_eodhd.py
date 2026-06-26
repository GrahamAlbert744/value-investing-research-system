"""
Validate outputs/universe_master.csv against EODHD exchange-symbol-list.

This is Phase 7C:
- fetch US common-stock exchange metadata from EODHD
- validate seed tickers against EODHD Code values
- preserve useful exchange metadata for later universe expansion

Outputs:
- outputs/universe_validation_report.csv
- outputs/eodhd_exchange_symbol_matches.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.eodhd_client import EODHDClient
from src.universe_validation import (
    exchange_symbols_to_dataframe,
    load_universe_master,
    validate_universe_against_exchange_symbols,
)


def main() -> None:
    universe_path = PROJECT_ROOT / "outputs" / "universe_master.csv"
    validation_output_path = PROJECT_ROOT / "outputs" / "universe_validation_report.csv"
    matches_output_path = PROJECT_ROOT / "outputs" / "eodhd_exchange_symbol_matches.csv"

    exchange_code = "US"
    security_type = "common_stock"

    print(f"Loading universe master: {universe_path}")
    universe_df = load_universe_master(universe_path)

    print(f"Fetching EODHD exchange symbols: exchange={exchange_code}, type={security_type}")
    client = EODHDClient.from_env()
    symbols = client.get_exchange_symbols(
        exchange_code=exchange_code,
        security_type=security_type,
        include_delisted=False,
    )

    exchange_symbols_df = exchange_symbols_to_dataframe(symbols)

    report = validate_universe_against_exchange_symbols(
        universe_df=universe_df,
        exchange_symbols_df=exchange_symbols_df,
        exchange_suffix=exchange_code,
    )

    report.to_csv(validation_output_path, index=False)

    matched_codes = set(report.loc[report["found_in_eodhd_exchange_symbols"], "code"])
    matches_df = exchange_symbols_df[
        exchange_symbols_df["eodhd_code_upper"].isin(matched_codes)
    ].copy()

    matches_df.to_csv(matches_output_path, index=False)

    print(f"\nUniverse validation report saved to: {validation_output_path}")
    print(f"EODHD matched metadata saved to: {matches_output_path}")
    print(f"Universe tickers checked: {len(report)}")
    print(f"Found in EODHD exchange symbols: {int(report['found_in_eodhd_exchange_symbols'].sum())}")
    print(f"Missing from EODHD exchange symbols: {int((~report['found_in_eodhd_exchange_symbols']).sum())}")

    print("\nValidation status counts:")
    print(report["validation_status"].value_counts().to_string())

    issues = report[report["validation_status"] != "pass"]

    if issues.empty:
        print("\nIssues to review: none")
    else:
        print("\nIssues to review:")
        print(
            issues[
                [
                    "ticker",
                    "validation_status",
                    "validation_issues",
                    "universe_company_name",
                    "universe_currency",
                    "eodhd_name",
                    "eodhd_currency",
                    "eodhd_type",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()