"""
Tests for expanded EODHD normalized metrics data-quality checks.

These tests use small fake DataFrames and do not require:
- API access
- .env
- raw JSON files
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.data_quality import (
    check_allowed_values,
    check_boolean_bad_values,
    check_date_staleness,
    check_metadata_warning_fields,
    check_numeric_bounds,
    check_required_fields,
    is_missing,
    load_data_quality_rules,
    parse_date,
    run_data_quality_checks,
    safe_float,
    status_for_issue,
)


def test_load_data_quality_rules_reads_yaml(tmp_path: Path):
    rules_path = tmp_path / "data_quality_rules.yml"

    rules = {
        "required_fields": [
            {
                "field": "ticker",
                "severity": "critical",
                "decision": "reject",
                "description": "Ticker is required.",
            }
        ]
    }

    with rules_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(rules, file)

    loaded = load_data_quality_rules(rules_path)

    assert loaded["required_fields"][0]["field"] == "ticker"
    assert loaded["required_fields"][0]["severity"] == "critical"


def test_load_data_quality_rules_missing_file_raises_error(tmp_path: Path):
    missing_path = tmp_path / "missing_data_quality_rules.yml"

    with pytest.raises(FileNotFoundError):
        load_data_quality_rules(missing_path)


def test_is_missing_detects_none_blank_and_nan():
    assert is_missing(None)
    assert is_missing("")
    assert is_missing("   ")
    assert is_missing(float("nan"))
    assert not is_missing("AAPL")
    assert not is_missing(0)


def test_safe_float_converts_valid_numbers():
    assert safe_float("10.5") == 10.5
    assert safe_float(42) == 42.0
    assert safe_float(None) is None
    assert safe_float("not_a_number") is None


def test_parse_date_parses_valid_date_and_returns_none_for_invalid():
    parsed = parse_date("2026-06-30")

    assert parsed is not None
    assert parsed.year == 2026
    assert parse_date("not_a_date") is None
    assert parse_date(None) is None


def test_status_for_issue_maps_severity_to_status():
    assert status_for_issue("critical") == "fail"
    assert status_for_issue("high") == "fail"
    assert status_for_issue("medium") == "flag"
    assert status_for_issue("low") == "flag"


def test_check_required_fields_passes_when_values_exist():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "name": "Apple Inc",
                "sector": "Technology",
            }
        ]
    )

    rules = [
        {
            "field": "ticker",
            "severity": "critical",
            "decision": "reject",
            "description": "Ticker is required.",
        },
        {
            "field": "name",
            "severity": "critical",
            "decision": "reject",
            "description": "Name is required.",
        },
    ]

    report = check_required_fields(df, rules)

    assert len(report) == 2
    assert all(row["status"] == "pass" for row in report)
    assert all(row["rows_affected"] == 0 for row in report)


def test_check_required_fields_fails_when_values_missing():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "name": "",
            }
        ]
    )

    rules = [
        {
            "field": "ticker",
            "severity": "critical",
            "decision": "reject",
            "description": "Ticker is required.",
        },
        {
            "field": "name",
            "severity": "critical",
            "decision": "reject",
            "description": "Name is required.",
        },
        {
            "field": "sector",
            "severity": "high",
            "decision": "flag",
            "description": "Sector is required.",
        },
    ]

    report = check_required_fields(df, rules)

    name_result = next(row for row in report if row["field"] == "name")
    sector_result = next(row for row in report if row["field"] == "sector")

    assert name_result["status"] == "fail"
    assert name_result["issue"] == "missing_values"
    assert name_result["rows_affected"] == 1
    assert name_result["decision"] == "reject"

    assert sector_result["status"] == "fail"
    assert sector_result["issue"] == "field_missing_from_dataset"
    assert sector_result["rows_affected"] == 1
    assert sector_result["decision"] == "flag"


def test_check_numeric_bounds_passes_valid_values():
    df = pd.DataFrame(
        [
            {
                "market_capitalization": 3000000000000,
                "pe_ratio": 30.5,
            }
        ]
    )

    rules = [
        {
            "field": "market_capitalization",
            "min_value": 1,
            "max_value": None,
            "severity": "critical",
            "decision": "reject",
            "description": "Market cap must be positive.",
        },
        {
            "field": "pe_ratio",
            "min_value": 0,
            "max_value": 200,
            "severity": "medium",
            "decision": "flag",
            "description": "PE should be in a reasonable range.",
        },
    ]

    report = check_numeric_bounds(df, rules)

    assert len(report) == 2
    assert all(row["status"] == "pass" for row in report)
    assert all(row["rows_affected"] == 0 for row in report)


def test_check_numeric_bounds_uses_fail_for_high_and_flag_for_medium():
    df = pd.DataFrame(
        [
            {
                "market_capitalization": -100,
                "pe_ratio": 500,
            }
        ]
    )

    rules = [
        {
            "field": "market_capitalization",
            "min_value": 1,
            "max_value": None,
            "severity": "high",
            "decision": "reject",
            "description": "Market cap must be positive.",
        },
        {
            "field": "pe_ratio",
            "min_value": 0,
            "max_value": 200,
            "severity": "medium",
            "decision": "flag",
            "description": "PE should be in a reasonable range.",
        },
    ]

    report = check_numeric_bounds(df, rules)

    assert len(report) == 2

    market_cap_result = next(
        row for row in report if row["field"] == "market_capitalization"
    )
    pe_result = next(row for row in report if row["field"] == "pe_ratio")

    assert market_cap_result["status"] == "fail"
    assert market_cap_result["issue"] == "outside_expected_bounds_or_missing"
    assert market_cap_result["rows_affected"] == 1
    assert market_cap_result["decision"] == "reject"

    assert pe_result["status"] == "flag"
    assert pe_result["issue"] == "outside_expected_bounds_or_missing"
    assert pe_result["rows_affected"] == 1
    assert pe_result["decision"] == "flag"


def test_check_numeric_bounds_skips_missing_field():
    df = pd.DataFrame([{"ticker": "AAPL"}])

    rules = [
        {
            "field": "market_capitalization",
            "min_value": 1,
            "max_value": None,
            "severity": "critical",
            "decision": "reject",
            "description": "Market cap must be positive.",
        }
    ]

    report = check_numeric_bounds(df, rules)

    assert len(report) == 1
    assert report[0]["status"] == "skip"
    assert report[0]["issue"] == "field_missing_from_dataset"


def test_check_allowed_values_passes_allowed_security_type():
    df = pd.DataFrame([{"security_type": "Common Stock"}])

    rules = [
        {
            "field": "security_type",
            "allowed_values": ["Common Stock", "common_stock"],
            "severity": "critical",
            "decision": "reject",
            "description": "Only common stocks allowed.",
        }
    ]

    report = check_allowed_values(df, rules)

    assert report[0]["status"] == "pass"
    assert report[0]["rows_affected"] == 0


def test_check_allowed_values_fails_disallowed_security_type():
    df = pd.DataFrame([{"security_type": "ETF"}])

    rules = [
        {
            "field": "security_type",
            "allowed_values": ["Common Stock", "common_stock"],
            "severity": "critical",
            "decision": "reject",
            "description": "Only common stocks allowed.",
        }
    ]

    report = check_allowed_values(df, rules)

    assert report[0]["status"] == "fail"
    assert report[0]["issue"] == "value_not_allowed_or_missing"
    assert report[0]["rows_affected"] == 1


def test_check_boolean_bad_values_passes_when_not_bad():
    df = pd.DataFrame([{"is_delisted": False}])

    rules = [
        {
            "field": "is_delisted",
            "bad_values": [True, "true", "1", 1],
            "severity": "critical",
            "decision": "reject",
            "description": "Delisted securities excluded.",
        }
    ]

    report = check_boolean_bad_values(df, rules)

    assert report[0]["status"] == "pass"
    assert report[0]["rows_affected"] == 0


def test_check_boolean_bad_values_fails_when_bad():
    df = pd.DataFrame([{"is_delisted": "true"}])

    rules = [
        {
            "field": "is_delisted",
            "bad_values": [True, "true", "1", 1],
            "severity": "critical",
            "decision": "reject",
            "description": "Delisted securities excluded.",
        }
    ]

    report = check_boolean_bad_values(df, rules)

    assert report[0]["status"] == "fail"
    assert report[0]["issue"] == "bad_boolean_flag_detected"
    assert report[0]["rows_affected"] == 1


def test_check_date_staleness_passes_recent_date():
    df = pd.DataFrame([{"fundamentals_updated_at": "2026-06-01"}])

    rules = [
        {
            "field": "fundamentals_updated_at",
            "max_age_days": 180,
            "severity": "high",
            "decision": "flag",
            "description": "Fundamentals should be recent.",
        }
    ]

    report = check_date_staleness(
        df=df,
        date_rules=rules,
        as_of=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )

    assert report[0]["status"] == "pass"
    assert report[0]["rows_affected"] == 0


def test_check_date_staleness_fails_stale_date():
    df = pd.DataFrame([{"fundamentals_updated_at": "2025-01-01"}])

    rules = [
        {
            "field": "fundamentals_updated_at",
            "max_age_days": 180,
            "severity": "high",
            "decision": "flag",
            "description": "Fundamentals should be recent.",
        }
    ]

    report = check_date_staleness(
        df=df,
        date_rules=rules,
        as_of=datetime(2026, 6, 30, tzinfo=timezone.utc),
    )

    assert report[0]["status"] == "fail"
    assert report[0]["issue"] == "date_missing_or_stale"
    assert report[0]["rows_affected"] == 1


def test_check_metadata_warning_fields_flags_missing_metadata():
    df = pd.DataFrame([{"isin": None}])

    rules = [
        {
            "field": "isin",
            "severity": "medium",
            "decision": "flag",
            "description": "ISIN helps identify duplicate risks.",
        }
    ]

    report = check_metadata_warning_fields(
        df=df,
        rules=rules,
        rule_type="duplicate_risk_fields",
    )

    assert report[0]["status"] == "flag"
    assert report[0]["issue"] == "metadata_missing"
    assert report[0]["rows_affected"] == 1


def test_run_data_quality_checks_runs_all_rule_types():
    df = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "ticker": "AAPL.US",
                "name": "Apple Inc",
                "security_type": "Common Stock",
                "is_delisted": False,
                "market_capitalization": 3000000000000,
                "fundamentals_updated_at": "2099-01-01",
                "isin": "US0378331005",
                "beta": 1.1,
            }
        ]
    )

    rules = {
        "required_fields": [
            {
                "field": "source_symbol",
                "severity": "critical",
                "decision": "reject",
                "description": "Source symbol required.",
            }
        ],
        "numeric_bounds": [
            {
                "field": "market_capitalization",
                "min_value": 1,
                "max_value": None,
                "severity": "critical",
                "decision": "reject",
                "description": "Market cap positive.",
            }
        ],
        "allowed_values": [
            {
                "field": "security_type",
                "allowed_values": ["Common Stock"],
                "severity": "critical",
                "decision": "reject",
                "description": "Common stocks only.",
            }
        ],
        "boolean_flags": [
            {
                "field": "is_delisted",
                "bad_values": [True, "true", "1", 1],
                "severity": "critical",
                "decision": "reject",
                "description": "Delisted excluded.",
            }
        ],
        "date_staleness": [
            {
                "field": "fundamentals_updated_at",
                "max_age_days": 180,
                "severity": "high",
                "decision": "flag",
                "description": "Fundamentals freshness.",
            }
        ],
        "duplicate_risk_fields": [
            {
                "field": "isin",
                "severity": "medium",
                "decision": "flag",
                "description": "ISIN duplicate risk.",
            }
        ],
        "soft_warning_fields": [
            {
                "field": "beta",
                "severity": "low",
                "decision": "allow",
                "description": "Beta optional.",
            }
        ],
    }

    report = run_data_quality_checks(df, rules)

    assert isinstance(report, pd.DataFrame)
    assert not report.empty
    assert set(report["rule_type"]) == {
        "required_field",
        "numeric_bounds",
        "allowed_values",
        "boolean_flags",
        "date_staleness",
        "duplicate_risk_fields",
        "soft_warning_fields",
    }
    assert (report["status"] == "pass").all()