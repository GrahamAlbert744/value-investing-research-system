"""
Tests for EODHD financial statement extraction.

These tests use small fake dictionaries and temporary files, so they do not require:
- API access
- .env
- raw EODHD JSON files
"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.financials import (
    build_financial_statement_coverage,
    build_quality_flags,
    extract_statement_lines,
    get_nested_value,
    infer_raw_value_type,
    infer_source_symbol_from_fundamentals,
    load_financial_statement_config,
    safe_numeric,
    standardize_period_type,
)


def minimal_financial_statement_config() -> dict:
    """Return a small financial statement extraction config for tests."""
    return {
        "statement_sections": {
            "income_statement": {
                "raw_path": "Financials.Income_Statement",
                "eodhd_name": "Income_Statement",
            },
            "balance_sheet": {
                "raw_path": "Financials.Balance_Sheet",
                "eodhd_name": "Balance_Sheet",
            },
            "cash_flow": {
                "raw_path": "Financials.Cash_Flow",
                "eodhd_name": "Cash_Flow",
            },
        },
        "period_types": {
            "yearly": {
                "standard_period_type": "annual",
            },
            "quarterly": {
                "standard_period_type": "quarterly",
            },
        },
    }


def minimal_fundamentals_data() -> dict:
    """Return fake EODHD-style fundamentals data with financial statements."""
    return {
        "General": {
            "Code": "AAPL",
            "Exchange": "US",
            "PrimaryTicker": "AAPL.US",
            "Name": "Apple Inc",
        },
        "Financials": {
            "Income_Statement": {
                "currency_symbol": "USD",
                "yearly": {
                    "2023-09-30": {
                        "date": "2023-09-30",
                        "filing_date": "2023-11-03",
                        "totalRevenue": 383285000000,
                        "netIncome": 96995000000,
                    },
                    "2022-09-30": {
                        "date": "2022-09-30",
                        "filing_date": "2022-10-28",
                        "totalRevenue": 394328000000,
                        "netIncome": 99803000000,
                    },
                },
                "quarterly": {
                    "2023-06-30": {
                        "date": "2023-06-30",
                        "filing_date": "2023-08-04",
                        "totalRevenue": 81797000000,
                        "netIncome": 19881000000,
                    }
                },
            },
            "Balance_Sheet": {
                "currency_symbol": "USD",
                "yearly": {
                    "2023-09-30": {
                        "date": "2023-09-30",
                        "filing_date": "2023-11-03",
                        "totalAssets": 352583000000,
                        "totalLiab": 290437000000,
                    }
                },
                "quarterly": {},
            },
            "Cash_Flow": {
                "currency_symbol": "USD",
                "yearly": {
                    "2023-09-30": {
                        "date": "2023-09-30",
                        "filing_date": "2023-11-03",
                        "totalCashFromOperatingActivities": 110543000000,
                        "capitalExpenditures": -10959000000,
                        "freeCashFlow": 99584000000,
                    }
                },
                "quarterly": {},
            },
        },
    }


def test_load_financial_statement_config_reads_yaml(tmp_path: Path):
    config_path = tmp_path / "financial_statement_config.yml"
    config = minimal_financial_statement_config()

    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file)

    loaded = load_financial_statement_config(config_path)

    assert loaded["statement_sections"]["income_statement"]["raw_path"] == (
        "Financials.Income_Statement"
    )


def test_load_financial_statement_config_missing_file_raises_error(tmp_path: Path):
    missing_path = tmp_path / "missing_financial_statement_config.yml"

    with pytest.raises(FileNotFoundError):
        load_financial_statement_config(missing_path)


def test_get_nested_value_returns_existing_nested_dict():
    data = minimal_fundamentals_data()

    result = get_nested_value(data, "Financials.Income_Statement")

    assert isinstance(result, dict)
    assert "yearly" in result


def test_get_nested_value_returns_none_for_missing_path():
    data = minimal_fundamentals_data()

    result = get_nested_value(data, "Financials.Not_A_Statement")

    assert result is None


def test_infer_source_symbol_from_fundamentals_uses_primary_ticker_first():
    data = minimal_fundamentals_data()

    result = infer_source_symbol_from_fundamentals(data)

    assert result == "AAPL.US"


def test_infer_source_symbol_from_fundamentals_uses_code_and_exchange():
    data = minimal_fundamentals_data()
    data["General"].pop("PrimaryTicker")

    result = infer_source_symbol_from_fundamentals(data)

    assert result == "AAPL.US"


def test_infer_source_symbol_from_fundamentals_falls_back_to_unknown():
    data = {"General": {}}

    result = infer_source_symbol_from_fundamentals(data)

    assert result == "UNKNOWN"


def test_standardize_period_type_maps_yearly_to_annual():
    config = minimal_financial_statement_config()

    assert standardize_period_type("yearly", config) == "annual"
    assert standardize_period_type("quarterly", config) == "quarterly"


def test_safe_numeric_converts_valid_values():
    assert safe_numeric("123.45") == 123.45
    assert safe_numeric(100) == 100.0
    assert safe_numeric(-50) == -50.0


def test_safe_numeric_returns_none_for_invalid_values():
    assert safe_numeric(None) is None
    assert safe_numeric("") is None
    assert safe_numeric("not_a_number") is None


def test_infer_raw_value_type_labels_values():
    assert infer_raw_value_type(None) == "null"
    assert infer_raw_value_type(True) == "bool"
    assert infer_raw_value_type(1) == "int"
    assert infer_raw_value_type(1.5) == "float"
    assert infer_raw_value_type("text") == "str"


def test_build_quality_flags_identifies_basic_issues():
    flags = build_quality_flags(
        line_item="totalRevenue",
        value=-100,
        value_numeric=-100.0,
        line_items={"date": "2023-09-30"},
    )

    assert "negative_revenue" in flags
    assert "missing_filing_date" in flags


def test_extract_statement_lines_creates_long_format_rows():
    data = minimal_fundamentals_data()
    config = minimal_financial_statement_config()

    result = extract_statement_lines(data=data, config=config)

    assert isinstance(result, pd.DataFrame)
    assert not result.empty

    expected_columns = {
        "source_symbol",
        "statement_type",
        "raw_period_type",
        "period_type",
        "fiscal_date",
        "reported_date",
        "filing_date",
        "currency",
        "statement_currency_source",
        "line_item",
        "value",
        "value_numeric",
        "raw_value_type",
        "quality_flags",
        "source_path",
        "extracted_at_utc",
    }

    assert expected_columns.issubset(set(result.columns))
    assert "income_statement" in set(result["statement_type"])
    assert "balance_sheet" in set(result["statement_type"])
    assert "cash_flow" in set(result["statement_type"])

    assert "yearly" in set(result["raw_period_type"])
    assert "annual" in set(result["period_type"])
    assert "quarterly" in set(result["period_type"])

    revenue_row = result[
        (result["statement_type"] == "income_statement")
        & (result["raw_period_type"] == "yearly")
        & (result["period_type"] == "annual")
        & (result["fiscal_date"] == "2023-09-30")
        & (result["line_item"] == "totalRevenue")
    ].iloc[0]

    assert revenue_row["source_symbol"] == "AAPL.US"
    assert revenue_row["currency"] == "USD"
    assert revenue_row["statement_currency_source"] == (
        "Financials.Income_Statement.currency_symbol"
    )
    assert revenue_row["value_numeric"] == 383285000000.0
    assert revenue_row["raw_value_type"] == "int"
    assert revenue_row["source_path"] == (
        "Financials.Income_Statement.yearly.2023-09-30.totalRevenue"
    )


def test_extract_statement_lines_uses_source_symbol_override():
    data = minimal_fundamentals_data()
    config = minimal_financial_statement_config()

    result = extract_statement_lines(
        data=data,
        config=config,
        source_symbol="REQUESTED_AAPL.US",
    )

    assert set(result["source_symbol"]) == {"REQUESTED_AAPL.US"}


def test_extract_statement_lines_returns_empty_dataframe_without_financials():
    data = {"General": {"Code": "AAPL", "Exchange": "US"}}
    config = minimal_financial_statement_config()

    result = extract_statement_lines(data=data, config=config)

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_build_financial_statement_coverage_summarizes_statement_periods():
    data = minimal_fundamentals_data()
    config = minimal_financial_statement_config()

    statement_lines = extract_statement_lines(data=data, config=config)
    coverage = build_financial_statement_coverage(statement_lines)

    assert isinstance(coverage, pd.DataFrame)
    assert not coverage.empty

    income_annual = coverage[
        (coverage["statement_type"] == "income_statement")
        & (coverage["raw_period_type"] == "yearly")
        & (coverage["period_type"] == "annual")
    ].iloc[0]

    assert income_annual["source_symbol"] == "AAPL.US"
    assert income_annual["period_count"] == 2
    assert income_annual["latest_fiscal_date"] == "2023-09-30"
    assert income_annual["earliest_fiscal_date"] == "2022-09-30"
    assert income_annual["currency"] == "USD"


def test_build_financial_statement_coverage_handles_empty_input():
    statement_lines = pd.DataFrame()

    coverage = build_financial_statement_coverage(statement_lines)

    assert isinstance(coverage, pd.DataFrame)
    assert coverage.empty
    assert list(coverage.columns) == [
        "source_symbol",
        "statement_type",
        "raw_period_type",
        "period_type",
        "period_count",
        "line_count",
        "latest_fiscal_date",
        "earliest_fiscal_date",
        "currency",
    ]