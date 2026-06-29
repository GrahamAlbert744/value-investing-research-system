"""
Financial statement data-quality checks.

This module checks:
- whether required statement coverage exists
- whether required line items exist
- whether numeric line items are actually numeric
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_financial_statement_quality_rules(rules_path: Path) -> dict[str, Any]:
    """Load financial statement quality rules from YAML."""
    if not rules_path.exists():
        raise FileNotFoundError(
            f"Financial statement quality rules file not found: {rules_path}"
        )

    with rules_path.open("r", encoding="utf-8") as file:
        rules = yaml.safe_load(file)

    if not isinstance(rules, dict):
        raise TypeError("Financial statement quality rules must load as a dictionary.")

    return rules


def is_missing(value: Any) -> bool:
    """Return True if a value should be treated as missing."""
    if value is None:
        return True

    try:
        if pd.isna(value):
            return True
    except TypeError:
        pass

    if isinstance(value, str) and value.strip() == "":
        return True

    return False


def status_for_issue(severity: str) -> str:
    """Convert severity to a report status."""
    if severity.lower() in {"critical", "high"}:
        return "fail"

    return "flag"


def check_required_coverage(
    coverage_df: pd.DataFrame,
    required_coverage: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check whether required statement coverage exists."""
    results: list[dict[str, Any]] = []

    for rule in required_coverage:
        statement_type = rule["statement_type"]
        period_type = rule["period_type"]
        min_periods = int(rule["min_periods"])
        severity = rule.get("severity", "medium")
        description = rule.get("description", "")

        if coverage_df.empty:
            results.append(
                {
                    "rule_type": "required_coverage",
                    "statement_type": statement_type,
                    "period_type": period_type,
                    "line_item": "",
                    "severity": severity,
                    "status": status_for_issue(severity),
                    "issue": "coverage_table_empty",
                    "description": description,
                    "observed_value": 0,
                    "expected_value": min_periods,
                    "rows_affected": 0,
                }
            )
            continue

        subset = coverage_df[
            (coverage_df["statement_type"] == statement_type)
            & (coverage_df["period_type"] == period_type)
        ]

        if subset.empty:
            results.append(
                {
                    "rule_type": "required_coverage",
                    "statement_type": statement_type,
                    "period_type": period_type,
                    "line_item": "",
                    "severity": severity,
                    "status": status_for_issue(severity),
                    "issue": "coverage_row_missing",
                    "description": description,
                    "observed_value": 0,
                    "expected_value": min_periods,
                    "rows_affected": 0,
                }
            )
            continue

        observed_periods = int(subset.iloc[0]["period_count"])

        if observed_periods >= min_periods:
            status = "pass"
            issue = ""
        else:
            status = status_for_issue(severity)
            issue = "insufficient_period_coverage"

        results.append(
            {
                "rule_type": "required_coverage",
                "statement_type": statement_type,
                "period_type": period_type,
                "line_item": "",
                "severity": severity,
                "status": status,
                "issue": issue,
                "description": description,
                "observed_value": observed_periods,
                "expected_value": min_periods,
                "rows_affected": 0 if status == "pass" else 1,
            }
        )

    return results


def check_required_line_items(
    statement_lines: pd.DataFrame,
    required_line_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check whether required line items are present."""
    results: list[dict[str, Any]] = []

    for rule in required_line_items:
        statement_type = rule["statement_type"]
        period_type = rule["period_type"]
        line_item = rule["line_item"]
        severity = rule.get("severity", "medium")
        description = rule.get("description", "")

        if statement_lines.empty:
            results.append(
                {
                    "rule_type": "required_line_item",
                    "statement_type": statement_type,
                    "period_type": period_type,
                    "line_item": line_item,
                    "severity": severity,
                    "status": status_for_issue(severity),
                    "issue": "statement_lines_empty",
                    "description": description,
                    "observed_value": 0,
                    "expected_value": 1,
                    "rows_affected": 0,
                }
            )
            continue

        subset = statement_lines[
            (statement_lines["statement_type"] == statement_type)
            & (statement_lines["period_type"] == period_type)
            & (statement_lines["line_item"] == line_item)
        ]

        if subset.empty:
            status = status_for_issue(severity)
            issue = "required_line_item_missing"
            observed_value = 0
            rows_affected = 1
        else:
            status = "pass"
            issue = ""
            observed_value = int(len(subset))
            rows_affected = 0

        results.append(
            {
                "rule_type": "required_line_item",
                "statement_type": statement_type,
                "period_type": period_type,
                "line_item": line_item,
                "severity": severity,
                "status": status,
                "issue": issue,
                "description": description,
                "observed_value": observed_value,
                "expected_value": 1,
                "rows_affected": rows_affected,
            }
        )

    return results


def check_non_numeric_statement_values(
    statement_lines: pd.DataFrame,
    allowed_non_numeric_line_items: list[str],
) -> list[dict[str, Any]]:
    """
    Check whether non-metadata line items have numeric values.

    Date and filing-date fields are allowed to be nonnumeric.
    """
    if statement_lines.empty:
        return [
            {
                "rule_type": "numeric_statement_values",
                "statement_type": "",
                "period_type": "",
                "line_item": "",
                "severity": "high",
                "status": "fail",
                "issue": "statement_lines_empty",
                "description": "No statement lines are available to check for numeric values.",
                "observed_value": 0,
                "expected_value": "numeric values for financial line items",
                "rows_affected": 0,
            }
        ]

    allowed = {item.lower() for item in allowed_non_numeric_line_items}

    check_df = statement_lines.copy()
    check_df["line_item_lower"] = check_df["line_item"].astype(str).str.lower()

    numeric_candidates = check_df[~check_df["line_item_lower"].isin(allowed)].copy()

    if numeric_candidates.empty:
        return [
            {
                "rule_type": "numeric_statement_values",
                "statement_type": "",
                "period_type": "",
                "line_item": "",
                "severity": "medium",
                "status": "skip",
                "issue": "no_numeric_candidate_rows",
                "description": "No candidate numeric rows were available after excluding metadata fields.",
                "observed_value": 0,
                "expected_value": "numeric candidate rows",
                "rows_affected": 0,
            }
        ]

    invalid_mask = numeric_candidates["value"].apply(lambda value: not is_missing(value)) & (
        numeric_candidates["value_numeric"].isna()
    )

    invalid_rows = numeric_candidates[invalid_mask]
    invalid_count = int(len(invalid_rows))

    if invalid_count == 0:
        status = "pass"
        issue = ""
    else:
        status = "flag"
        issue = "non_numeric_financial_values"

    return [
        {
            "rule_type": "numeric_statement_values",
            "statement_type": "",
            "period_type": "",
            "line_item": "",
            "severity": "medium",
            "status": status,
            "issue": issue,
            "description": "Financial statement line items should generally have numeric values, excluding metadata fields.",
            "observed_value": invalid_count,
            "expected_value": 0,
            "rows_affected": invalid_count,
        }
    ]


def run_financial_statement_quality_checks(
    statement_lines: pd.DataFrame,
    coverage_df: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Run all configured financial statement data-quality checks."""
    all_results: list[dict[str, Any]] = []

    all_results.extend(
        check_required_coverage(
            coverage_df=coverage_df,
            required_coverage=rules.get("required_coverage", []),
        )
    )

    all_results.extend(
        check_required_line_items(
            statement_lines=statement_lines,
            required_line_items=rules.get("required_line_items", []),
        )
    )

    all_results.extend(
        check_non_numeric_statement_values(
            statement_lines=statement_lines,
            allowed_non_numeric_line_items=rules.get(
                "allowed_non_numeric_line_items",
                [],
            ),
        )
    )

    report = pd.DataFrame(all_results)

    if report.empty:
        return report

    return report.sort_values(
        by=["status", "severity", "rule_type", "statement_type", "period_type", "line_item"],
        ascending=True,
    )