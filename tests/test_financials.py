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
    extract_statement_lines,
    get_nested_value,
    infer_source_symbol_from_fundamentals,
    load_financial_statement_config,
    safe_numeric,
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
        "period_types": ["yearly", "quarterly"],
    }


def minimal_fundamentals_data() -> dict:
    """Return fake EODHD-style fundamentals data with financial statements."""
    return {
        "General": {
            "Code": "AAPL",
            "Exchange": "US",
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

    result = get_nested_value(data, "Financials.Missing_Statement")

    assert result is None


def test_infer_source_symbol_from_fundamentals_uses_code_and_exchange():
    data = minimal_fundamentals_data()

    result = infer_source_symbol_from_fundamentals(data)

    assert result == "AAPL.US"


def test_infer_source_symbol_from_fundamentals_falls_back_to_unknown():
    data = {"General": {}}

    result = infer_source_symbol_from_fundamentals(data)

    assert result == "UNKNOWN"


def test_safe_numeric_converts_valid_values():
    assert safe_numeric("10.5") == 10.5
    assert safe_numeric(42) == 42.0
    assert safe_numeric(-100) == -100.0


def test_safe_numeric_returns_none_for_invalid_values():
    assert safe_numeric(None) is None
    assert safe_numeric("") is None
    assert safe_numeric("not_a_number") is None


def test_extract_statement_lines_creates_long_format_rows():
    data = minimal_fundamentals_data()
    config = minimal_financial_statement_config()

    result = extract_statement_lines(data=data, config=config)

    assert isinstance(result, pd.DataFrame)
    assert not result.empty

    expected_columns = {
        "source_symbol",
        "statement_type",
        "period_type",
        "fiscal_date",
        "currency",
        "line_item",
        "value",
        "value_numeric",
        "source_path",
        "extracted_at_utc",
    }

    assert expected_columns.issubset(set(result.columns))
    assert "income_statement" in set(result["statement_type"])
    assert "balance_sheet" in set(result["statement_type"])
    assert "cash_flow" in set(result["statement_type"])
    assert "yearly" in set(result["period_type"])
    assert "quarterly" in set(result["period_type"])
    assert "totalRevenue" in set(result["line_item"])
    assert "freeCashFlow" in set(result["line_item"])


def test_extract_statement_lines_uses_source_symbol_override():
    data = minimal_fundamentals_data()
    config = minimal_financial_statement_config()

    result = extract_statement_lines(
        data=data,
        config=config,
        source_symbol="TEST.US",
    )

    assert set(result["source_symbol"]) == {"TEST.US"}


def test_extract_statement_lines_returns_empty_dataframe_without_financials():
    data = {
        "General": {
            "Code": "AAPL",
            "Exchange": "US",
        }
    }
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

    income_yearly = coverage[
        (coverage["statement_type"] == "income_statement")
        & (coverage["period_type"] == "yearly")
    ].iloc[0]

    assert income_yearly["source_symbol"] == "AAPL.US"
    assert income_yearly["period_count"] == 2
    assert income_yearly["latest_fiscal_date"] == "2023-09-30"
    assert income_yearly["earliest_fiscal_date"] == "2022-09-30"
    assert income_yearly["currency"] == "USD"


def test_build_financial_statement_coverage_handles_empty_input():
    statement_lines = pd.DataFrame()

    coverage = build_financial_statement_coverage(statement_lines)

    assert isinstance(coverage, pd.DataFrame)
    assert coverage.empty
    assert list(coverage.columns) == [
        "source_symbol",
        "statement_type",
        "period_type",
        "period_count",
        "line_count",
        "latest_fiscal_date",
        "earliest_fiscal_date",
        "currency",
    ]