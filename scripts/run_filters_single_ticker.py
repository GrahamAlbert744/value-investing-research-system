"""
Run MVP hard filters for one normalized ticker.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.field_mapping import flatten_normalized_fields, normalize_ticker_fields  # noqa: E402
from src.filters import run_hard_filters  # noqa: E402


OUTPUT_DIR = Path("outputs/reports")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="AAPL.US")
    args = parser.parse_args()

    normalized = normalize_ticker_fields(args.ticker)
    values = flatten_normalized_fields(normalized)

    filter_result = run_hard_filters(values)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_path = OUTPUT_DIR / f"{args.ticker}_hard_filter_summary.json"
    details_path = OUTPUT_DIR / f"{args.ticker}_hard_filter_details.csv"

    summary = {
        "ticker": args.ticker,
        "passed": filter_result["passed"],
        "is_financial_sector": filter_result["is_financial_sector"],
    }

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    details_df = pd.DataFrame(filter_result["results"])
    details_df.to_csv(details_path, index=False)

    print(json.dumps(summary, indent=2))
    print()
    print(details_df.to_string(index=False))
    print()
    print(f"Saved summary to {summary_path}")
    print(f"Saved details to {details_path}")


if __name__ == "__main__":
    main()