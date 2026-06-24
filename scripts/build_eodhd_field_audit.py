"""
Build outputs/eodhd_field_audit.csv from the latest raw EODHD fundamentals JSON.

This script:
1. Finds the latest fundamentals JSON in outputs/raw_samples/
2. Flattens the nested JSON structure
3. Saves a field audit CSV to outputs/eodhd_field_audit.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from trackers.eodhd_field_audit import create_field_audit


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


def main() -> None:
    raw_samples_dir = PROJECT_ROOT / "outputs" / "raw_samples"
    output_path = PROJECT_ROOT / "outputs" / "eodhd_field_audit.csv"

    latest_json_path = find_latest_fundamentals_json(raw_samples_dir)

    print(f"Using raw JSON sample: {latest_json_path}")

    with latest_json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    audit_df = create_field_audit(data)

    audit_df.to_csv(output_path, index=False)

    print(f"Field audit saved to: {output_path}")
    print(f"Rows in audit: {len(audit_df)}")

    print("\nTop-level fields audited:")
    for field in sorted(audit_df["top_level_field"].dropna().unique()):
        print(f"- {field}")


if __name__ == "__main__":
    main()