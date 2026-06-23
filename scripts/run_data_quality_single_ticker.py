"""
Run data-quality checks for one normalized ticker.

MVP purpose:
- Normalize saved EODHD raw fields.
- Run data-quality checks.
- Export a field-level data-quality report.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.data_quality import run_data_quality_checks  # noqa: E402
from src.field_mapping import flatten_normalized_fields, normalize_ticker_fields  # noqa: E402


OUTPUT_DIR = Path("outputs/reports")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="AAPL.US")
    args = parser.parse_args()

    normalized = normalize_ticker_fields(args.ticker)
    values = flatten_normalized_fields(normalized)

    flags = run_data_quality_checks(args.ticker, values)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / f"{args.ticker}_data_quality_report.csv"
    df = pd.DataFrame(flags)

    if df.empty:
        print(f"No data-quality flags found for {args.ticker}.")
        df = pd.DataFrame(
            columns=[
                "ticker",
                "field",
                "issue_type",
                "severity",
                "explanation",
                "recommended_action",
            ]
        )
    else:
        print(df.to_string(index=False))

    df.to_csv(output_path, index=False)
    print(f"\nSaved data-quality report to {output_path}")


if __name__ == "__main__":
    main()