"""
Tests for universe construction.

These tests use small fake DataFrames and temporary files so they do not require:
- API access
- .env
- raw EODHD JSON files
"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.universe import (
    build_exclusion_reason,
    build_universe_master,
    load_seed_universe,
    load_universe_config,
    normalize_include_flag,
    split_ticker,
    validate_required_columns,
)


def minimal_universe_config() -> dict:
    """Return a small test config for universe construction."""
    return {
        "allowed_exchange_suffixes": ["US"],
        "required_columns": [
            "ticker",
            "company_name",
            "sector",
            "industry",
            "country",
            "currency",
            "exchange_suffix",
            "include_in_mvp",
        ],
        "excluded_categories": {
            "fossil_fuels": {
                "keywords": ["oil", "gas", "coal", "petroleum"]
            },
            "defense": {
                "keywords": ["defense", "weapons", "military"]
            },
            "tobacco": {
                "keywords": ["tobacco", "cigarettes"]
            },
            "gambling": {
                "keywords": ["casino", "betting", "wagering"]
            },
        },
        "default_flags": {
            "is_seed_universe": True,
            "data_source": "manual_seed",
        },
    }


def test_split_ticker_with_exchange_suffix():
    code, suffix = split_ticker("AAPL.US")

    assert code == "AAPL"
    assert suffix == "US"


def test_split_ticker_without_exchange_suffix():
    code, suffix = split_ticker("AAPL")

    assert code == "AAPL"
    assert suffix is None


def test_split_ticker_handles_blank_value():
    code, suffix = split_ticker("")

    assert code == ""
    assert suffix is None


def test_normalize_include_flag_true_values():
    assert normalize_include_flag("yes")
    assert normalize_include_flag("true")
    assert normalize_include_flag("1")
    assert normalize_include_flag("y")
    assert normalize_include_flag(True)


def test_normalize_include_flag_false_values():
    assert not normalize_include_flag("no")
    assert not normalize_include_flag("false")
    assert not normalize_include_flag("0")
    assert not normalize_include_flag("")
    assert not normalize_include_flag(None)
    assert not normalize_include_flag(False)


def test_validate_required_columns_returns_missing_columns():
    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "company_name": "Apple Inc",
            }
        ]
    )

    required_columns = ["ticker", "company_name", "sector"]

    missing = validate_required_columns(df, required_columns)

    assert missing == ["sector"]


def test_build_exclusion_reason_uses_manual_reason_first():
    config = minimal_universe_config()

    row = pd.Series(
        {
            "company_name": "Example Company",
            "sector": "Technology",
            "industry": "Software",
            "manual_exclusion_reason": "manual_do_not_include",
            "notes": "",
        }
    )

    result = build_exclusion_reason(row, config)

    assert result == "manual_do_not_include"


def test_build_exclusion_reason_detects_excluded_keyword():
    config = minimal_universe_config()

    row = pd.Series(
        {
            "company_name": "Example Oil Company",
            "sector": "Energy",
            "industry": "Oil & Gas",
            "manual_exclusion_reason": "",
            "notes": "",
        }
    )

    result = build_exclusion_reason(row, config)

    assert result == "excluded_category:fossil_fuels"


def test_build_exclusion_reason_returns_blank_for_allowed_company():
    config = minimal_universe_config()

    row = pd.Series(
        {
            "company_name": "Apple Inc",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "manual_exclusion_reason": "",
            "notes": "Seed test company",
        }
    )

    result = build_exclusion_reason(row, config)

    assert result == ""


def test_build_universe_master_includes_valid_seed_company():
    config = minimal_universe_config()

    seed_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "company_name": "Apple Inc",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "country": "United States",
                "currency": "USD",
                "exchange_suffix": "US",
                "include_in_mvp": "yes",
                "manual_exclusion_reason": "",
                "notes": "Seed test company",
            }
        ]
    )

    result = build_universe_master(seed_df, config)

    assert len(result) == 1
    assert result.loc[0, "ticker"] == "AAPL.US"
    assert result.loc[0, "code"] == "AAPL"
    assert result.loc[0, "exchange_suffix"] == "US"
    assert bool(result.loc[0, "include_in_universe"]) is True
    assert result.loc[0, "exclusion_reason"] == ""


def test_build_universe_master_excludes_disallowed_exchange():
    config = minimal_universe_config()

    seed_df = pd.DataFrame(
        [
            {
                "ticker": "RY.TO",
                "company_name": "Royal Bank of Canada",
                "sector": "Financial Services",
                "industry": "Banks",
                "country": "Canada",
                "currency": "CAD",
                "exchange_suffix": "TO",
                "include_in_mvp": "yes",
                "manual_exclusion_reason": "",
                "notes": "Non-US test company",
            }
        ]
    )

    result = build_universe_master(seed_df, config)

    assert bool(result.loc[0, "exchange_allowed"]) is False
    assert bool(result.loc[0, "include_in_universe"]) is False


def test_build_universe_master_excludes_keyword_category():
    config = minimal_universe_config()

    seed_df = pd.DataFrame(
        [
            {
                "ticker": "FAKE.US",
                "company_name": "Fake Oil Company",
                "sector": "Energy",
                "industry": "Oil & Gas",
                "country": "United States",
                "currency": "USD",
                "exchange_suffix": "US",
                "include_in_mvp": "yes",
                "manual_exclusion_reason": "",
                "notes": "Should be excluded",
            }
        ]
    )

    result = build_universe_master(seed_df, config)

    assert result.loc[0, "exclusion_reason"] == "excluded_category:fossil_fuels"
    assert bool(result.loc[0, "passes_manual_filters"]) is False
    assert bool(result.loc[0, "include_in_universe"]) is False


def test_build_universe_master_raises_error_for_missing_required_columns():
    config = minimal_universe_config()

    seed_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "company_name": "Apple Inc",
            }
        ]
    )

    with pytest.raises(ValueError):
        build_universe_master(seed_df, config)


def test_load_universe_config_reads_yaml(tmp_path: Path):
    config_path = tmp_path / "universe_config.yml"
    config = minimal_universe_config()

    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file)

    loaded = load_universe_config(config_path)

    assert loaded["allowed_exchange_suffixes"] == ["US"]


def test_load_universe_config_missing_file_raises_error(tmp_path: Path):
    missing_path = tmp_path / "missing_universe_config.yml"

    with pytest.raises(FileNotFoundError):
        load_universe_config(missing_path)


def test_load_seed_universe_reads_csv(tmp_path: Path):
    seed_path = tmp_path / "universe_seed.csv"

    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "company_name": "Apple Inc",
            }
        ]
    )

    df.to_csv(seed_path, index=False)

    loaded = load_seed_universe(seed_path)

    assert loaded.loc[0, "ticker"] == "AAPL.US"
    assert loaded.loc[0, "company_name"] == "Apple Inc"


def test_load_seed_universe_missing_file_raises_error(tmp_path: Path):
    missing_path = tmp_path / "missing_universe_seed.csv"

    with pytest.raises(FileNotFoundError):
        load_seed_universe(missing_path)