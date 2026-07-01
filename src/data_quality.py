"""
Expanded data-quality checks for normalized EODHD metrics.

Checks include:
- missing required fields
- numeric values outside expected bounds
- allowed-value checks
- boolean bad-value checks
- date staleness checks
- duplicate-risk metadata checks
- soft warning fields

The module preserves backward compatibility with the original tests:
- check_required_fields(df, rules)
- check_numeric_bounds(df, rules)
- run_data_quality_checks(df, rules)
"""

from __future__ import annotations

from datetime import datetime, timezone
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


def parse_date(value: Any) -> pd.Timestamp | None:
    """Parse a date-like value safely."""
    if is_missing(value):
        return None

    parsed = pd.to_datetime(value, errors="coerce", utc=True)

    if pd.isna(parsed):
        return None

    return parsed


def status_for_issue(severity: str) -> str:
    """Convert severity to report status."""
    severity_lower = str(severity).lower()

    if severity_lower in {"critical", "high"}:
        return "fail"

    return "flag"


def make_result(
    rule_type: str,
    field: str,
    severity: str,
    status: str,
    issue: str,
    description: str,
    rows_affected: int,
    decision: str = "",
    observed_value: Any = "",
    expected_value: Any = "",
) -> dict[str, Any]:
    """Create a standardized data-quality result row."""
    return {
        "rule_type": rule_type,
        "field": field,
        "severity": severity,
        "decision": decision,
        "status": status,
        "issue": issue,
        "description": description,
        "rows_affected": int(rows_affected),
        "observed_value": observed_value,
        "expected_value": expected_value,
    }


def check_required_fields(
    df: pd.DataFrame,
    required_fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check whether required fields exist and are populated."""
    results: list[dict[str, Any]] = []

    for rule in required_fields:
        field = rule["field"]
        severity = rule.get("severity", "medium")
        decision = rule.get("decision", "")
        description = rule.get("description", "")

        if field not in df.columns:
            results.append(
                make_result(
                    rule_type="required_field",
                    field=field,
                    severity=severity,
                    decision=decision,
                    status="fail",
                    issue="field_missing_from_dataset",
                    description=description,
                    rows_affected=len(df),
                    expected_value="field_present",
                )
            )
            continue

        missing_count = int(df[field].apply(is_missing).sum())
        status = "pass" if missing_count == 0 else "fail"

        results.append(
            make_result(
                rule_type="required_field",
                field=field,
                severity=severity,
                decision=decision,
                status=status,
                issue="" if status == "pass" else "missing_values",
                description=description,
                rows_affected=missing_count,
                observed_value=missing_count,
                expected_value=0,
            )
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
        decision = rule.get("decision", "")
        description = rule.get("description", "")

        if field not in df.columns:
            results.append(
                make_result(
                    rule_type="numeric_bounds",
                    field=field,
                    severity=severity,
                    decision=decision,
                    status="skip",
                    issue="field_missing_from_dataset",
                    description=description,
                    rows_affected=len(df),
                )
            )
            continue

        values = df[field].apply(safe_float)

        invalid_mask = values.isna()

        if min_value is not None:
            invalid_mask = invalid_mask | (values < float(min_value))

        if max_value is not None:
            invalid_mask = invalid_mask | (values > float(max_value))

        affected_count = int(invalid_mask.sum())
        status = "pass" if affected_count == 0 else status_for_issue(severity)

        results.append(
            make_result(
                rule_type="numeric_bounds",
                field=field,
                severity=severity,
                decision=decision,
                status=status,
                issue="" if status == "pass" else "outside_expected_bounds_or_missing",
                description=description,
                rows_affected=affected_count,
                observed_value=affected_count,
                expected_value=f"min={min_value}, max={max_value}",
            )
        )

    return results


def check_allowed_values(
    df: pd.DataFrame,
    allowed_value_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check whether fields contain only allowed values."""
    results: list[dict[str, Any]] = []

    for rule in allowed_value_rules:
        field = rule["field"]
        allowed_values = {str(value).strip().lower() for value in rule["allowed_values"]}
        severity = rule.get("severity", "medium")
        decision = rule.get("decision", "")
        description = rule.get("description", "")

        if field not in df.columns:
            results.append(
                make_result(
                    rule_type="allowed_values",
                    field=field,
                    severity=severity,
                    decision=decision,
                    status="skip",
                    issue="field_missing_from_dataset",
                    description=description,
                    rows_affected=len(df),
                )
            )
            continue

        invalid_mask = df[field].apply(
            lambda value: is_missing(value)
            or str(value).strip().lower() not in allowed_values
        )

        affected_count = int(invalid_mask.sum())
        status = "pass" if affected_count == 0 else status_for_issue(severity)

        results.append(
            make_result(
                rule_type="allowed_values",
                field=field,
                severity=severity,
                decision=decision,
                status=status,
                issue="" if status == "pass" else "value_not_allowed_or_missing",
                description=description,
                rows_affected=affected_count,
                observed_value=affected_count,
                expected_value=",".join(sorted(allowed_values)),
            )
        )

    return results


def check_boolean_bad_values(
    df: pd.DataFrame,
    boolean_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Check boolean-like fields for explicitly bad values."""
    results: list[dict[str, Any]] = []

    for rule in boolean_rules:
        field = rule["field"]
        bad_values = {str(value).strip().lower() for value in rule.get("bad_values", [])}
        severity = rule.get("severity", "medium")
        decision = rule.get("decision", "")
        description = rule.get("description", "")

        if field not in df.columns:
            results.append(
                make_result(
                    rule_type="boolean_flags",
                    field=field,
                    severity=severity,
                    decision=decision,
                    status="skip",
                    issue="field_missing_from_dataset",
                    description=description,
                    rows_affected=len(df),
                )
            )
            continue

        bad_mask = df[field].apply(
            lambda value: False if is_missing(value) else str(value).strip().lower() in bad_values
        )

        affected_count = int(bad_mask.sum())
        status = "pass" if affected_count == 0 else status_for_issue(severity)

        results.append(
            make_result(
                rule_type="boolean_flags",
                field=field,
                severity=severity,
                decision=decision,
                status=status,
                issue="" if status == "pass" else "bad_boolean_flag_detected",
                description=description,
                rows_affected=affected_count,
                observed_value=affected_count,
                expected_value="no bad values",
            )
        )

    return results


def check_date_staleness(
    df: pd.DataFrame,
    date_rules: list[dict[str, Any]],
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """Check whether date fields are stale."""
    results: list[dict[str, Any]] = []

    if as_of is None:
        as_of_timestamp = pd.Timestamp(datetime.now(timezone.utc))
    else:
        as_of_timestamp = pd.Timestamp(as_of)
        if as_of_timestamp.tzinfo is None:
            as_of_timestamp = as_of_timestamp.tz_localize("UTC")

    for rule in date_rules:
        field = rule["field"]
        max_age_days = int(rule["max_age_days"])
        severity = rule.get("severity", "medium")
        decision = rule.get("decision", "")
        description = rule.get("description", "")

        if field not in df.columns:
            results.append(
                make_result(
                    rule_type="date_staleness",
                    field=field,
                    severity=severity,
                    decision=decision,
                    status="skip",
                    issue="field_missing_from_dataset",
                    description=description,
                    rows_affected=len(df),
                    expected_value=f"age <= {max_age_days} days",
                )
            )
            continue

        parsed_dates = df[field].apply(parse_date)

        def is_stale(parsed_date: pd.Timestamp | None) -> bool:
            if parsed_date is None:
                return True

            age_days = (as_of_timestamp - parsed_date).days
            return age_days > max_age_days

        stale_mask = parsed_dates.apply(is_stale)
        affected_count = int(stale_mask.sum())
        status = "pass" if affected_count == 0 else status_for_issue(severity)

        max_observed_age = ""
        valid_dates = [date for date in parsed_dates.tolist() if date is not None]
        if valid_dates:
            max_observed_age = max((as_of_timestamp - date).days for date in valid_dates)

        results.append(
            make_result(
                rule_type="date_staleness",
                field=field,
                severity=severity,
                decision=decision,
                status=status,
                issue="" if status == "pass" else "date_missing_or_stale",
                description=description,
                rows_affected=affected_count,
                observed_value=max_observed_age,
                expected_value=f"age <= {max_age_days} days",
            )
        )

    return results


def check_metadata_warning_fields(
    df: pd.DataFrame,
    rules: list[dict[str, Any]],
    rule_type: str,
) -> list[dict[str, Any]]:
    """Check useful metadata fields and warn if missing."""
    results: list[dict[str, Any]] = []

    for rule in rules:
        field = rule["field"]
        severity = rule.get("severity", "low")
        decision = rule.get("decision", "flag")
        description = rule.get("description", "")

        if field not in df.columns:
            results.append(
                make_result(
                    rule_type=rule_type,
                    field=field,
                    severity=severity,
                    decision=decision,
                    status="skip",
                    issue="field_missing_from_dataset",
                    description=description,
                    rows_affected=len(df),
                )
            )
            continue

        missing_count = int(df[field].apply(is_missing).sum())
        status = "pass" if missing_count == 0 else status_for_issue(severity)

        results.append(
            make_result(
                rule_type=rule_type,
                field=field,
                severity=severity,
                decision=decision,
                status=status,
                issue="" if status == "pass" else "metadata_missing",
                description=description,
                rows_affected=missing_count,
                observed_value=missing_count,
                expected_value=0,
            )
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

    all_results.extend(
        check_allowed_values(
            df=df,
            allowed_value_rules=rules.get("allowed_values", []),
        )
    )

    all_results.extend(
        check_boolean_bad_values(
            df=df,
            boolean_rules=rules.get("boolean_flags", []),
        )
    )

    all_results.extend(
        check_date_staleness(
            df=df,
            date_rules=rules.get("date_staleness", []),
        )
    )

    all_results.extend(
        check_metadata_warning_fields(
            df=df,
            rules=rules.get("duplicate_risk_fields", []),
            rule_type="duplicate_risk_fields",
        )
    )

    all_results.extend(
        check_metadata_warning_fields(
            df=df,
            rules=rules.get("soft_warning_fields", []),
            rule_type="soft_warning_fields",
        )
    )

    report = pd.DataFrame(all_results)

    if report.empty:
        return report

    status_order = {
        "fail": 0,
        "flag": 1,
        "skip": 2,
        "pass": 3,
    }

    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }

    report["_status_order"] = report["status"].map(status_order).fillna(9)
    report["_severity_order"] = report["severity"].map(
        lambda value: severity_order.get(str(value).lower(), 9)
    )

    report = report.sort_values(
        by=["_status_order", "_severity_order", "rule_type", "field"],
        ascending=True,
    ).drop(columns=["_status_order", "_severity_order"])

    return report