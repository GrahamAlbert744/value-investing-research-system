"""
Build financial-statement summary metrics for scoring and valuation.

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

from src.financial_statement_summary import summarize_all_symbols


STATEMENT_LINES_PATH = PROJECT_ROOT / "outputs" / "financial_statement_lines.csv"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "financial_statement_summary.csv"


def main() -> None:
    if not STATEMENT_LINES_PATH.exists():
        raise FileNotFoundError(
            f"Missing financial statement lines file: {STATEMENT_LINES_PATH}\n"
            "Run scripts\\extract_financial_statements.py first."
        )

    print(f"Loading financial statement lines: {STATEMENT_LINES_PATH}")

    statement_lines = pd.read_csv(STATEMENT_LINES_PATH)

    print(f"Rows loaded: {len(statement_lines)}")
    print(f"Columns loaded: {len(statement_lines.columns)}")

    summary = summarize_all_symbols(statement_lines)

    summary.to_csv(OUTPUT_PATH, index=False)

    print(f"\nFinancial statement summary saved to: {OUTPUT_PATH}")
    print(f"Summary rows: {len(summary)}")
    print(f"Summary columns: {len(summary.columns)}")

    if not summary.empty:
        print("\nSummary columns:")
        for column in summary.columns:
            print(f"- {column}")

        flag_column = "summary_quality_flags"
        if flag_column in summary.columns:
            print("\nSummary quality flags:")
            print(summary[["source_symbol", flag_column]].to_string(index=False))


if __name__ == "__main__":
    main()