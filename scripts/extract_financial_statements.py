"""
Extract EODHD financial statements from the latest raw fundamentals JSON.

Inputs:
- outputs/raw_samples/fundamentals_*.json
- config/financial_statement_config.yml

Outputs:
- outputs/financial_statement_lines.csv
- outputs/financial_statement_coverage.csv
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.financials import (
    build_financial_statement_coverage,
    extract_statement_lines,
    load_financial_statement_config,
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


def main() -> None:
    raw_samples_dir = PROJECT_ROOT / "outputs" / "raw_samples"
    config_path = PROJECT_ROOT / "config" / "financial_statement_config.yml"
    lines_output_path = PROJECT_ROOT / "outputs" / "financial_statement_lines.csv"
    coverage_output_path = PROJECT_ROOT / "outputs" / "financial_statement_coverage.csv"

    latest_json_path = find_latest_fundamentals_json(raw_samples_dir)

    print(f"Using raw fundamentals JSON: {latest_json_path}")
    print(f"Using financial statement config: {config_path}")

    with latest_json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    config = load_financial_statement_config(config_path)

    statement_lines = extract_statement_lines(data=data, config=config)
    coverage = build_financial_statement_coverage(statement_lines)

    statement_lines.to_csv(lines_output_path, index=False)
    coverage.to_csv(coverage_output_path, index=False)

    print(f"\nFinancial statement lines saved to: {lines_output_path}")
    print(f"Financial statement coverage saved to: {coverage_output_path}")

    print(f"\nRows extracted: {len(statement_lines)}")
    print(f"Coverage rows: {len(coverage)}")

    if statement_lines.empty:
        print("\nNo financial statement rows found. Check raw JSON Financials structure.")
    else:
        print("\nStatement coverage:")
        print(coverage.to_string(index=False))

        print("\nStatement types extracted:")
        print(statement_lines["statement_type"].value_counts().to_string())

        print("\nPeriod types extracted:")
        print(statement_lines["period_type"].value_counts().to_string())


if __name__ == "__main__":
    main()