"""
Build financial statement summary metrics for scoring.

Input:
- outputs/financial_statement_lines.csv

Output:
- outputs/financial_statement_summary.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.financial_statement_summary import build_financial_statement_summary


def main() -> None:
    input_path = PROJECT_ROOT / "outputs" / "financial_statement_lines.csv"
    output_path = PROJECT_ROOT / "outputs" / "financial_statement_summary.csv"

    if not input_path.exists():
        raise FileNotFoundError(
            f"Missing financial statement lines file: {input_path}\n"
            "Run scripts\\extract_financial_statements.py first."
        )

    print(f"Loading financial statement lines: {input_path}")

    statement_lines = pd.read_csv(input_path)

    summary = build_financial_statement_summary(statement_lines)
    summary.to_csv(output_path, index=False)

    print(f"\nFinancial statement summary saved to: {output_path}")
    print(f"Rows written: {len(summary)}")

    if summary.empty:
        print("\nNo summary rows created.")
    else:
        print("\nSummary columns:")
        for column in summary.columns:
            print(f"- {column}")

        print("\nPreview:")
        print(summary.head().to_string(index=False))


if __name__ == "__main__":
    main()