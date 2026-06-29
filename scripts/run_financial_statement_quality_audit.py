"""
Run financial statement data-quality checks.

Inputs:
- outputs/financial_statement_lines.csv
- outputs/financial_statement_coverage.csv
- config/financial_statement_quality_rules.yml

Output:
- outputs/financial_statement_quality_report.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.financial_statement_quality import (
    load_financial_statement_quality_rules,
    run_financial_statement_quality_checks,
)


def main() -> None:
    lines_path = PROJECT_ROOT / "outputs" / "financial_statement_lines.csv"
    coverage_path = PROJECT_ROOT / "outputs" / "financial_statement_coverage.csv"
    rules_path = PROJECT_ROOT / "config" / "financial_statement_quality_rules.yml"
    output_path = PROJECT_ROOT / "outputs" / "financial_statement_quality_report.csv"

    if not lines_path.exists() or not coverage_path.exists():
        raise FileNotFoundError(
            "Missing financial statement extraction outputs.\n"
            "Run scripts\\extract_financial_statements.py first."
        )

    print(f"Loading statement lines: {lines_path}")
    print(f"Loading statement coverage: {coverage_path}")
    print(f"Loading quality rules: {rules_path}")

    statement_lines = pd.read_csv(lines_path)
    coverage_df = pd.read_csv(coverage_path)
    rules = load_financial_statement_quality_rules(rules_path)

    report = run_financial_statement_quality_checks(
        statement_lines=statement_lines,
        coverage_df=coverage_df,
        rules=rules,
    )

    report.to_csv(output_path, index=False)

    print(f"\nFinancial statement quality report saved to: {output_path}")
    print(f"Rules evaluated: {len(report)}")

    if not report.empty:
        print("\nStatus counts:")
        print(report["status"].value_counts().to_string())

        issues = report[report["status"].isin(["fail", "flag"])]

        print("\nIssues to review:")
        if issues.empty:
            print("None")
        else:
            print(
                issues[
                    [
                        "rule_type",
                        "statement_type",
                        "period_type",
                        "line_item",
                        "severity",
                        "status",
                        "issue",
                        "observed_value",
                        "expected_value",
                    ]
                ].to_string(index=False)
            )


if __name__ == "__main__":
    main()