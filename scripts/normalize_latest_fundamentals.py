"""
Normalize the latest raw EODHD fundamentals JSON into outputs/normalized_metrics.csv.

This script:
1. Finds the latest fundamentals_*.json file in outputs/raw_samples/
2. Loads config/field_mapping.yml
3. Normalizes the raw JSON into one flat row
4. Saves outputs/normalized_metrics.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.normalization import (
    load_field_mapping,
    normalize_fundamentals,
    summarize_missing_values,
)


def find_latest_fundamentals_json(raw_samples_dir: Path) -> Path:
    """Find the most recent fundamentals JSON sample."""
    files = sorted(
        raw_samples_dir.glob("fundamentals_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise FileNotFoundError(
            f"No fundamentals_*.json files found in {raw_samples_dir}. "
            "Run scripts\\inspect_eodhd_fields.py first."
        )

    return files[0]


def infer_source_symbol_from_filename(path: Path) -> str:
    """
    Infer source symbol from filename.

    Example:
    fundamentals_AAPL_US_20260625_120000.json -> AAPL.US
    """
    name = path.stem

    if name.startswith("fundamentals_"):
        parts = name.replace("fundamentals_", "").split("_")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"

    return "UNKNOWN"


def main() -> None:
    raw_samples_dir = PROJECT_ROOT / "outputs" / "raw_samples"
    mapping_path = PROJECT_ROOT / "config" / "field_mapping.yml"
    output_path = PROJECT_ROOT / "outputs" / "normalized_metrics.csv"

    latest_json_path = find_latest_fundamentals_json(raw_samples_dir)
    source_symbol = infer_source_symbol_from_filename(latest_json_path)

    print(f"Using raw JSON sample: {latest_json_path}")
    print(f"Inferred source symbol: {source_symbol}")
    print(f"Using field mapping: {mapping_path}")

    with latest_json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    field_mapping = load_field_mapping(mapping_path)

    row = normalize_fundamentals(
        data=data,
        field_mapping=field_mapping,
        source_symbol=source_symbol,
    )

    summary = summarize_missing_values(row)

    df = pd.DataFrame([row])
    df.to_csv(output_path, index=False)

    print(f"\nNormalized metrics saved to: {output_path}")
    print(f"Columns written: {len(df.columns)}")
    print(f"Total fields: {summary['total_fields']}")
    print(f"Missing fields: {summary['missing_fields']}")
    print(f"Non-missing fields: {summary['non_missing_fields']}")

    print("\nNormalized columns:")
    for column in df.columns:
        print(f"- {column}")


if __name__ == "__main__":
    main()