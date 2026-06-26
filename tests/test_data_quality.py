"""
Tests for EODHD normalized metrics data-quality checks.

These tests use small fake DataFrames and do not require:
- API access
- .env
- raw JSON files
"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.data_quality import (
    check_numeric_bounds,
    check_required_fields,
    is_missing,
    load_data_quality_rules,
    run_data_quality_checks,
    safe_float,
)


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
            "severity": "high",
            "description": "Ticker is required.",
        },
        {
            "field": "name",
            "severity": "high",
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
            "severity": "high",
            "description": "Ticker is required.",
        },
        {
            "field": "name",
            "severity": "high",
            "description": "Name is required.",
        },
        {
            "field": "sector",
            "severity": "medium",
            "description": "Sector is required.",
        },
    ]

    report = check_required_fields(df, rules)

    name_result = next(row for row in report if row["field"] == "name")
    sector_result = next(row for row in report if row["field"] == "sector")

    assert name_result["status"] == "fail"
    assert name_result["issue"] == "missing_values"
    assert name_result["rows_affected"] == 1

    assert sector_result["status"] == "fail"
    assert sector_result["issue"] == "field_missing_from_dataset"
    assert sector_result["rows_affected"] == 1


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
            "severity": "high",
            "description": "Market cap must be positive.",
        },
        {
            "field": "pe_ratio",
            "min_value": 0,
            "max_value": 200,
            "severity": "medium",
            "description": "PE should be in a reasonable range.",
        },
    ]

    report = check_numeric_bounds(df, rules)

    assert len(report) == 2
    assert all(row["status"] == "pass" for row in report)
    assert all(row["rows_affected"] == 0 for row in report)


def test_check_numeric_bounds_flags_out_of_range_values():
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
            "description": "Market cap must be positive.",
        },
        {
            "field": "pe_ratio",
            "min_value": 0,
            "max_value": 200,
            "severity": "medium",
            "description": "PE should be in a reasonable range.",
        },
    ]

    report = check_numeric_bounds(df, rules)

    assert len(report) == 2
    assert all(row["status"] == "flag" for row in report)
    assert all(row["issue"] == "outside_expected_bounds_or_missing" for row in report)
    assert all(row["rows_affected"] == 1 for row in report)


def test_check_numeric_bounds_skips_missing_field():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
            }
        ]
    )

    rules = [
        {
            "field": "pe_ratio",
            "min_value": 0,
            "max_value": 200,
            "severity": "medium",
            "description": "PE should be in a reasonable range.",
        },
    ]

    report = check_numeric_bounds(df, rules)

    assert len(report) == 1
    assert report[0]["status"] == "skip"
    assert report[0]["issue"] == "field_missing_from_dataset"


def test_run_data_quality_checks_returns_dataframe():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "name": "Apple Inc",
                "market_capitalization": 3000000000000,
                "pe_ratio": 30.5,
            }
        ]
    )

    rules = {
        "required_fields": [
            {
                "field": "ticker",
                "severity": "high",
                "description": "Ticker required.",
            },
            {
                "field": "name",
                "severity": "high",
                "description": "Name required.",
            },
        ],
        "numeric_bounds": [
            {
                "field": "market_capitalization",
                "min_value": 1,
                "max_value": None,
                "severity": "high",
                "description": "Market cap positive.",
            },
            {
                "field": "pe_ratio",
                "min_value": 0,
                "max_value": 200,
                "severity": "medium",
                "description": "PE reasonable.",
            },
        ],
    }

    report = run_data_quality_checks(df, rules)

    assert isinstance(report, pd.DataFrame)
    assert len(report) == 4
    assert set(report["status"]) == {"pass"}


def test_load_data_quality_rules_reads_yaml(tmp_path: Path):
    rules_path = tmp_path / "data_quality_rules.yml"

    rules = {
        "required_fields": [
            {
                "field": "ticker",
                "severity": "high",
                "description": "Ticker required.",
            }
        ]
    }

    with rules_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(rules, file)

    loaded = load_data_quality_rules(rules_path)

    assert loaded["required_fields"][0]["field"] == "ticker"


def test_load_data_quality_rules_missing_file_raises_error(tmp_path: Path):
    missing_path = tmp_path / "missing_data_quality_rules.yml"

    with pytest.raises(FileNotFoundError):
        load_data_quality_rules(missing_path)