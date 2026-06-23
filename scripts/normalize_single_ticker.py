"""
Normalize saved EODHD raw fields for a single ticker.

MVP purpose:
- Read saved raw JSON from data/raw.
- Map EODHD source fields to project-standard names.
- Export normalized values and mapping metadata.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.field_mapping import flatten_normalized_fields, normalize_ticker_fields  # noqa: E402


OUTPUT_DIR = Path("outputs/reports")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="AAPL.US")
    args = parser.parse_args()

    normalized = normalize_ticker_fields(args.ticker)
    flat = flatten_normalized_fields(normalized)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metadata_rows = []
    for field, meta in normalized.items():
        metadata_rows.append(
            {
                "ticker": args.ticker,
                "normalized_field": field,
                "value": meta["value"],
                "source_section": meta["source_section"],
                "source_field": meta["source_field"],
                "is_missing": meta["is_missing"],
            }
        )

    metadata_df = pd.DataFrame(metadata_rows)

    metadata_output = OUTPUT_DIR / f"{args.ticker}_normalized_field_mapping.csv"
    values_output = OUTPUT_DIR / f"{args.ticker}_normalized_values.json"

    metadata_df.to_csv(metadata_output, index=False)
    values_output.write_text(json.dumps(flat, indent=2), encoding="utf-8")

    print(f"Saved mapping metadata to {metadata_output}")
    print(f"Saved normalized values to {values_output}")
    print()
    print(metadata_df.to_string(index=False))


if __name__ == "__main__":
    main()