"""
Run first-pass data-quality checks on normalized EODHD metrics.

Input:
- outputs/normalized_metrics.csv
- config/data_quality_rules.yml

Output:
- outputs/data_quality_report.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_quality import load_data_quality_rules, run_data_quality_checks


def main() -> None:
    input_path = PROJECT_ROOT / "outputs" / "normalized_metrics.csv"
    rules_path = PROJECT_ROOT / "config" / "data_quality_rules.yml"
    output_path = PROJECT_ROOT / "outputs" / "data_quality_report.csv"

    if not input_path.exists():
        raise FileNotFoundError(
            f"Missing normalized metrics file: {input_path}\n"
            "Run scripts\\normalize_latest_fundamentals.py first."
        )

    print(f"Loading normalized metrics: {input_path}")
    print(f"Loading data-quality rules: {rules_path}")

    df = pd.read_csv(input_path)
    rules = load_data_quality_rules(rules_path)

    report = run_data_quality_checks(df=df, rules=rules)
    report.to_csv(output_path, index=False)

    print(f"\nData-quality report saved to: {output_path}")
    print(f"Rules evaluated: {len(report)}")

    if not report.empty:
        print("\nStatus counts:")
        print(report["status"].value_counts().to_string())

        print("\nIssues to review:")
        issues = report[report["status"].isin(["fail", "flag"])]
        if issues.empty:
            print("None")
        else:
            print(
                issues[
                    [
                        "rule_type",
                        "field",
                        "severity",
                        "status",
                        "issue",
                        "rows_affected",
                    ]
                ].to_string(index=False)
            )


if __name__ == "__main__":
    main()