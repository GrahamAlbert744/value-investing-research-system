"""
Tests for universe validation against EODHD exchange-symbol metadata.

These tests use fake DataFrames and temporary files, so they do not require:
- API access
- .env
- raw EODHD JSON files
"""

from pathlib import Path

import pandas as pd
import pytest

from src.universe_validation import (
    build_eodhd_ticker,
    exchange_symbols_to_dataframe,
    load_universe_master,
    validate_universe_against_exchange_symbols,
)


def test_build_eodhd_ticker_uppercases_code_and_suffix():
    result = build_eodhd_ticker("aapl", "us")

    assert result == "AAPL.US"


def test_load_universe_master_reads_csv(tmp_path: Path):
    universe_path = tmp_path / "universe_master.csv"

    df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "code": "AAPL",
                "currency": "USD",
                "include_in_universe": True,
            }
        ]
    )
    df.to_csv(universe_path, index=False)

    loaded = load_universe_master(universe_path)

    assert loaded.loc[0, "ticker"] == "AAPL.US"
    assert loaded.loc[0, "code"] == "AAPL"


def test_load_universe_master_missing_file_raises_error(tmp_path: Path):
    missing_path = tmp_path / "missing_universe_master.csv"

    with pytest.raises(FileNotFoundError):
        load_universe_master(missing_path)


def test_exchange_symbols_to_dataframe_renames_common_eodhd_columns():
    symbols = [
        {
            "Code": "AAPL",
            "Name": "Apple Inc",
            "Country": "USA",
            "Exchange": "NASDAQ",
            "Currency": "USD",
            "Type": "Common Stock",
            "ISIN": "US0378331005",
        }
    ]

    result = exchange_symbols_to_dataframe(symbols)

    assert "eodhd_code" in result.columns
    assert "eodhd_name" in result.columns
    assert "eodhd_country" in result.columns
    assert "eodhd_exchange" in result.columns
    assert "eodhd_currency" in result.columns
    assert "eodhd_type" in result.columns
    assert "eodhd_isin" in result.columns
    assert result.loc[0, "eodhd_code"] == "AAPL"
    assert result.loc[0, "eodhd_code_upper"] == "AAPL"


def test_exchange_symbols_to_dataframe_handles_empty_list():
    result = exchange_symbols_to_dataframe([])

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_exchange_symbols_to_dataframe_raises_error_without_code_column():
    symbols = [
        {
            "Name": "Apple Inc",
            "Currency": "USD",
        }
    ]

    with pytest.raises(ValueError):
        exchange_symbols_to_dataframe(symbols)


def test_validate_universe_passes_when_code_and_currency_match():
    universe_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "code": "AAPL",
                "company_name": "Apple Inc",
                "currency": "USD",
                "include_in_universe": True,
            }
        ]
    )

    exchange_symbols_df = exchange_symbols_to_dataframe(
        [
            {
                "Code": "AAPL",
                "Name": "Apple Inc",
                "Country": "USA",
                "Exchange": "NASDAQ",
                "Currency": "USD",
                "Type": "Common Stock",
                "ISIN": "US0378331005",
            }
        ]
    )

    result = validate_universe_against_exchange_symbols(
        universe_df=universe_df,
        exchange_symbols_df=exchange_symbols_df,
        exchange_suffix="US",
    )

    assert len(result) == 1
    assert result.loc[0, "ticker"] == "AAPL.US"
    assert result.loc[0, "code"] == "AAPL"
    assert result.loc[0, "expected_eodhd_ticker"] == "AAPL.US"
    assert bool(result.loc[0, "found_in_eodhd_exchange_symbols"]) is True
    assert bool(result.loc[0, "currency_matches"]) is True
    assert result.loc[0, "validation_status"] == "pass"
    assert result.loc[0, "validation_issues"] == ""
    assert result.loc[0, "eodhd_name"] == "Apple Inc"


def test_validate_universe_flags_missing_eodhd_symbol():
    universe_df = pd.DataFrame(
        [
            {
                "ticker": "FAKE.US",
                "code": "FAKE",
                "company_name": "Fake Company",
                "currency": "USD",
                "include_in_universe": True,
            }
        ]
    )

    exchange_symbols_df = exchange_symbols_to_dataframe(
        [
            {
                "Code": "AAPL",
                "Name": "Apple Inc",
                "Currency": "USD",
            }
        ]
    )

    result = validate_universe_against_exchange_symbols(
        universe_df=universe_df,
        exchange_symbols_df=exchange_symbols_df,
        exchange_suffix="US",
    )

    assert bool(result.loc[0, "found_in_eodhd_exchange_symbols"]) is False
    assert result.loc[0, "validation_status"] == "flag"
    assert result.loc[0, "validation_issues"] == "missing_from_eodhd_exchange_symbols"


def test_validate_universe_flags_currency_mismatch():
    universe_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "code": "AAPL",
                "company_name": "Apple Inc",
                "currency": "CAD",
                "include_in_universe": True,
            }
        ]
    )

    exchange_symbols_df = exchange_symbols_to_dataframe(
        [
            {
                "Code": "AAPL",
                "Name": "Apple Inc",
                "Currency": "USD",
            }
        ]
    )

    result = validate_universe_against_exchange_symbols(
        universe_df=universe_df,
        exchange_symbols_df=exchange_symbols_df,
        exchange_suffix="US",
    )

    assert bool(result.loc[0, "found_in_eodhd_exchange_symbols"]) is True
    assert bool(result.loc[0, "currency_matches"]) is False
    assert result.loc[0, "validation_status"] == "flag"
    assert result.loc[0, "validation_issues"] == "currency_mismatch_or_missing"


def test_validate_universe_raises_error_for_empty_universe():
    universe_df = pd.DataFrame()

    exchange_symbols_df = exchange_symbols_to_dataframe(
        [
            {
                "Code": "AAPL",
                "Name": "Apple Inc",
                "Currency": "USD",
            }
        ]
    )

    with pytest.raises(ValueError):
        validate_universe_against_exchange_symbols(
            universe_df=universe_df,
            exchange_symbols_df=exchange_symbols_df,
            exchange_suffix="US",
        )


def test_validate_universe_raises_error_for_empty_exchange_symbols():
    universe_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "code": "AAPL",
                "company_name": "Apple Inc",
                "currency": "USD",
                "include_in_universe": True,
            }
        ]
    )

    exchange_symbols_df = pd.DataFrame()

    with pytest.raises(ValueError):
        validate_universe_against_exchange_symbols(
            universe_df=universe_df,
            exchange_symbols_df=exchange_symbols_df,
            exchange_suffix="US",
        )


def test_validate_universe_raises_error_for_missing_universe_columns():
    universe_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "company_name": "Apple Inc",
            }
        ]
    )

    exchange_symbols_df = exchange_symbols_to_dataframe(
        [
            {
                "Code": "AAPL",
                "Name": "Apple Inc",
                "Currency": "USD",
            }
        ]
    )

    with pytest.raises(ValueError):
        validate_universe_against_exchange_symbols(
            universe_df=universe_df,
            exchange_symbols_df=exchange_symbols_df,
            exchange_suffix="US",
        )


def test_validate_universe_raises_error_when_symbols_not_standardized():
    universe_df = pd.DataFrame(
        [
            {
                "ticker": "AAPL.US",
                "code": "AAPL",
                "company_name": "Apple Inc",
                "currency": "USD",
                "include_in_universe": True,
            }
        ]
    )

    exchange_symbols_df = pd.DataFrame(
        [
            {
                "Code": "AAPL",
                "Name": "Apple Inc",
                "Currency": "USD",
            }
        ]
    )

    with pytest.raises(ValueError):
        validate_universe_against_exchange_symbols(
            universe_df=universe_df,
            exchange_symbols_df=exchange_symbols_df,
            exchange_suffix="US",
        )