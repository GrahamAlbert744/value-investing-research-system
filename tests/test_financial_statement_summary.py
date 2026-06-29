"""
Tests for financial statement summary metrics.

These tests use small fake DataFrames and do not require:
- API access
- .env
- raw EODHD JSON files
"""

import math

import pandas as pd
import pytest

from src.financial_statement_summary import (
    build_financial_statement_summary,
    get_line_item_value,
    get_recent_fiscal_dates,
    safe_divide,
    summarize_one_symbol,
)


def sample_statement_lines_with_reported_fcf() -> pd.DataFrame:
    """Return fake long-format statement lines with reported free cash flow."""
    return pd.DataFrame(
        [
            # Latest income statement
            {
                "source_symbol": "AAPL.US",
                "statement_type": "income_statement",
                "period_type": "yearly",
                "fiscal_date": "2023-09-30",
                "currency": "USD",
                "line_item": "totalRevenue",
                "value_numeric": 1100.0,
            },
            {
                "source_symbol": "AAPL.US",
                "statement_type": "income_statement",
                "period_type": "yearly",
                "fiscal_date": "2023-09-30",
                "currency": "USD",
                "line_item": "netIncome",
                "value_numeric": 220.0,
            },
            # Prior income statement
            {
                "source_symbol": "AAPL.US",
                "statement_type": "income_statement",
                "period_type": "yearly",
                "fiscal_date": "2022-09-30",
                "currency": "USD",
                "line_item": "totalRevenue",
                "value_numeric": 1000.0,
            },
            {
                "source_symbol": "AAPL.US",
                "statement_type": "income_statement",
                "period_type": "yearly",
                "fiscal_date": "2022-09-30",
                "currency": "USD",
                "line_item": "netIncome",
                "value_numeric": 200.0,
            },
            # Latest cash flow
            {
                "source_symbol": "AAPL.US",
                "statement_type": "cash_flow",
                "period_type": "yearly",
                "fiscal_date": "2023-09-30",
                "currency": "USD",
                "line_item": "totalCashFromOperatingActivities",
                "value_numeric": 300.0,
            },
            {
                "source_symbol": "AAPL.US",
                "statement_type": "cash_flow",
                "period_type": "yearly",
                "fiscal_date": "2023-09-30",
                "currency": "USD",
                "line_item": "capitalExpenditures",
                "value_numeric": -50.0,
            },
            {
                "source_symbol": "AAPL.US",
                "statement_type": "cash_flow",
                "period_type": "yearly",
                "fiscal_date": "2023-09-30",
                "currency": "USD",
                "line_item": "freeCashFlow",
                "value_numeric": 250.0,
            },
            # Latest balance sheet
            {
                "source_symbol": "AAPL.US",
                "statement_type": "balance_sheet",
                "period_type": "yearly",
                "fiscal_date": "2023-09-30",
                "currency": "USD",
                "line_item": "totalAssets",
                "value_numeric": 5000.0,
            },
            {
                "source_symbol": "AAPL.US",
                "statement_type": "balance_sheet",
                "period_type": "yearly",
                "fiscal_date": "2023-09-30",
                "currency": "USD",
                "line_item": "totalLiab",
                "value_numeric": 3000.0,
            },
        ]
    )


def sample_statement_lines_without_reported_fcf() -> pd.DataFrame:
    """Return fake lines where FCF must be computed from CFO + capex."""
    df = sample_statement_lines_with_reported_fcf()

    return df[df["line_item"] != "freeCashFlow"].copy()


def test_safe_divide_returns_ratio_for_valid_values():
    assert safe_divide(10, 2) == 5.0
    assert safe_divide("10", "4") == 2.5


def test_safe_divide_returns_none_for_invalid_or_zero_denominator():
    assert safe_divide(None, 2) is None
    assert safe_divide(10, None) is None
    assert safe_divide(10, 0) is None
    assert safe_divide("bad", 2) is None


def test_get_line_item_value_returns_matching_value():
    df = sample_statement_lines_with_reported_fcf()

    result = get_line_item_value(
        df=df,
        statement_type="income_statement",
        period_type="yearly",
        fiscal_date="2023-09-30",
        line_item="totalRevenue",
    )

    assert result == 1100.0


def test_get_line_item_value_returns_none_for_missing_item():
    df = sample_statement_lines_with_reported_fcf()

    result = get_line_item_value(
        df=df,
        statement_type="income_statement",
        period_type="yearly",
        fiscal_date="2023-09-30",
        line_item="missingLineItem",
    )

    assert result is None


def test_get_line_item_value_returns_none_for_nan_value():
    df = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "statement_type": "income_statement",
                "period_type": "yearly",
                "fiscal_date": "2023-09-30",
                "line_item": "totalRevenue",
                "value_numeric": float("nan"),
            }
        ]
    )

    result = get_line_item_value(
        df=df,
        statement_type="income_statement",
        period_type="yearly",
        fiscal_date="2023-09-30",
        line_item="totalRevenue",
    )

    assert result is None


def test_get_recent_fiscal_dates_returns_most_recent_dates_first():
    df = sample_statement_lines_with_reported_fcf()

    result = get_recent_fiscal_dates(
        df=df,
        period_type="yearly",
        max_dates=2,
    )

    assert result == ["2023-09-30", "2022-09-30"]


def test_summarize_one_symbol_calculates_core_metrics_with_reported_fcf():
    df = sample_statement_lines_with_reported_fcf()

    result = summarize_one_symbol(df)

    assert result["source_symbol"] == "AAPL.US"
    assert result["currency"] == "USD"
    assert result["latest_yearly_fiscal_date"] == "2023-09-30"
    assert result["prior_yearly_fiscal_date"] == "2022-09-30"
    assert result["yearly_periods_available"] == 2

    assert result["latest_revenue"] == 1100.0
    assert result["prior_revenue"] == 1000.0
    assert math.isclose(result["revenue_growth_yoy"], 0.10)

    assert result["latest_net_income"] == 220.0
    assert result["prior_net_income"] == 200.0
    assert math.isclose(result["net_income_growth_yoy"], 0.10)
    assert math.isclose(result["latest_net_margin"], 0.20)

    assert result["latest_operating_cash_flow"] == 300.0
    assert result["latest_capital_expenditures"] == -50.0
    assert result["latest_free_cash_flow"] == 250.0
    assert result["free_cash_flow_source"] == "reported"
    assert math.isclose(result["latest_fcf_margin"], 250.0 / 1100.0)

    assert result["latest_total_assets"] == 5000.0
    assert result["latest_total_liabilities"] == 3000.0
    assert result["latest_equity_estimate"] == 2000.0
    assert math.isclose(result["latest_liabilities_to_assets"], 0.60)


def test_summarize_one_symbol_computes_fcf_when_reported_fcf_missing():
    df = sample_statement_lines_without_reported_fcf()

    result = summarize_one_symbol(df)

    assert result["latest_free_cash_flow"] == 250.0
    assert result["free_cash_flow_source"] == "computed_operating_cash_flow_plus_capex"


def test_summarize_one_symbol_raises_error_for_empty_input():
    df = pd.DataFrame()

    with pytest.raises(ValueError):
        summarize_one_symbol(df)


def test_build_financial_statement_summary_returns_one_row_per_symbol():
    aapl = sample_statement_lines_with_reported_fcf()

    msft = sample_statement_lines_with_reported_fcf().copy()
    msft["source_symbol"] = "MSFT.US"

    combined = pd.concat([aapl, msft], ignore_index=True)

    result = build_financial_statement_summary(combined)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert set(result["source_symbol"]) == {"AAPL.US", "MSFT.US"}


def test_build_financial_statement_summary_handles_empty_input():
    result = build_financial_statement_summary(pd.DataFrame())

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_build_financial_statement_summary_raises_error_for_missing_columns():
    df = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "statement_type": "income_statement",
            }
        ]
    )

    with pytest.raises(ValueError):
        build_financial_statement_summary(df)