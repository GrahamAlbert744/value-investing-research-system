"""
Data-quality checks for normalized EODHD metrics.

This module checks:
- missing required fields
- numeric values outside expected bounds
- fields that are missing from the dataset entirely
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_data_quality_rules(rules_path: Path) -> dict[str, Any]:
    """Load data-quality rules from YAML."""
    if not rules_path.exists():
        raise FileNotFoundError(f"Data-quality rules file not found: {rules_path}")

    with rules_path.open("r", encoding="utf-8") as file:
        rules = yaml.safe_load(file)

    if not isinstance(rules, dict):
        raise TypeError("Data-quality rules must load as a dictionary.")

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


def safe_float(value: Any) -> float | None:
    """Convert value to float when possible."""
    if is_missing(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_required_fields(
    df: pd.DataFrame,
    required_fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check whether required fields exist and are populated."""
    results: list[dict[str, Any]] = []

    for rule in required_fields:
        field = rule["field"]
        severity = rule.get("severity", "medium")
        description = rule.get("description", "")

        if field not in df.columns:
            results.append(
                {
                    "rule_type": "required_field",
                    "field": field,
                    "severity": severity,
                    "status": "fail",
                    "issue": "field_missing_from_dataset",
                    "description": description,
                    "rows_affected": len(df),
                }
            )
            continue

        missing_count = int(df[field].apply(is_missing).sum())
        status = "pass" if missing_count == 0 else "fail"

        results.append(
            {
                "rule_type": "required_field",
                "field": field,
                "severity": severity,
                "status": status,
                "issue": "" if status == "pass" else "missing_values",
                "description": description,
                "rows_affected": missing_count,
            }
        )

    return results


def check_numeric_bounds(
    df: pd.DataFrame,
    numeric_bounds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check whether numeric fields fall within configured bounds."""
    results: list[dict[str, Any]] = []

    for rule in numeric_bounds:
        field = rule["field"]
        min_value = rule.get("min_value")
        max_value = rule.get("max_value")
        severity = rule.get("severity", "medium")
        description = rule.get("description", "")

        if field not in df.columns:
            results.append(
                {
                    "rule_type": "numeric_bounds",
                    "field": field,
                    "severity": severity,
                    "status": "skip",
                    "issue": "field_missing_from_dataset",
                    "description": description,
                    "rows_affected": len(df),
                }
            )
            continue

        values = df[field].apply(safe_float)

        invalid_mask = values.isna()
        if min_value is not None:
            invalid_mask = invalid_mask | (values < float(min_value))
        if max_value is not None:
            invalid_mask = invalid_mask | (values > float(max_value))

        affected_count = int(invalid_mask.sum())
        status = "pass" if affected_count == 0 else "flag"

        results.append(
            {
                "rule_type": "numeric_bounds",
                "field": field,
                "severity": severity,
                "status": status,
                "issue": "" if status == "pass" else "outside_expected_bounds_or_missing",
                "description": description,
                "rows_affected": affected_count,
            }
        )

    return results


def run_data_quality_checks(
    df: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Run all configured data-quality checks."""
    all_results: list[dict[str, Any]] = []

    all_results.extend(
        check_required_fields(
            df=df,
            required_fields=rules.get("required_fields", []),
        )
    )

    all_results.extend(
        check_numeric_bounds(
            df=df,
            numeric_bounds=rules.get("numeric_bounds", []),
        )
    )

    report = pd.DataFrame(all_results)

    if report.empty:
        return report

    return report.sort_values(
        by=["status", "severity", "rule_type", "field"],
        ascending=True,
    )