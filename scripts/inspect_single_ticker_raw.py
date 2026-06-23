"""
Inspect saved raw EODHD JSON files for a single ticker.

MVP purpose:
- Read raw JSON files saved in data/raw.
- Summarize top-level fields returned by each EODHD section.
- Export a simple field audit CSV.
"""

import argparse
import json
from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("outputs/reports")


def load_json(path: Path) -> dict:
    """Load a JSON file as a dictionary."""
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_section(ticker: str, section: str) -> list[dict]:
    """Inspect one raw EODHD section file."""
    path = RAW_DIR / f"{ticker}_{section}.json"

    if not path.exists():
        return [
            {
                "ticker": ticker,
                "section": section,
                "field": None,
                "value_type": None,
                "is_present": False,
                "is_null": None,
                "example_value": None,
                "note": f"Missing raw file: {path}",
            }
        ]

    data = load_json(path)

    rows = []

    if not isinstance(data, dict):
        rows.append(
            {
                "ticker": ticker,
                "section": section,
                "field": None,
                "value_type": type(data).__name__,
                "is_present": True,
                "is_null": data is None,
                "example_value": str(data)[:120],
                "note": "Response is not a dictionary",
            }
        )
        return rows

    for field, value in data.items():
        rows.append(
            {
                "ticker": ticker,
                "section": section,
                "field": field,
                "value_type": type(value).__name__,
                "is_present": True,
                "is_null": value is None,
                "example_value": str(value)[:120],
                "note": "",
            }
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="AAPL.US")
    parser.add_argument(
        "--sections",
        nargs="+",
        default=[
            "General",
            "Highlights",
            "Valuation",
            "SharesStats",
            "SplitsDividends",
        ],
    )
    args = parser.parse_args()

    all_rows = []

    for section in args.sections:
        all_rows.extend(inspect_section(args.ticker, section))

    df = pd.DataFrame(all_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / f"{args.ticker}_field_audit.csv"
    df.to_csv(output_path, index=False)

    print(f"Saved field audit to {output_path}")
    print()
    print(df[["section", "field", "value_type", "is_null"]].to_string(index=False))


if __name__ == "__main__":
    main()