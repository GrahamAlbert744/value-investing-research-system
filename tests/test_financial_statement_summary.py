"""
Tests for financial statement summary metrics.

These tests use small fake DataFrames and do not require:
- API access
- .env
- raw EODHD JSON files
"""

import pandas as pd
import pytest

from src.financial_statement_summary import (
    calculate_cagr,
    calculate_growth,
    choose_free_cash_flow,
    count_positive_values,
    filter_annual_rows,
    get_line_item_value,
    get_recent_fiscal_dates,
    is_missing,
    safe_divide,
    safe_float,
    summarize_all_symbols,
    summarize_one_symbol,
)


def sample_statement_lines() -> pd.DataFrame:
    """Return C4-style long-format financial statement lines."""
    rows = []

    annual_dates = [
        "2023-09-30",
        "2022-09-30",
        "2021-09-30",
        "2020-09-30",
    ]

    revenue_values = {
        "2023-09-30": 400.0,
        "2022-09-30": 360.0,
        "2021-09-30": 330.0,
        "2020-09-30": 300.0,
    }

    net_income_values = {
        "2023-09-30": 100.0,
        "2022-09-30": 90.0,
        "2021-09-30": 80.0,
        "2020-09-30": 70.0,
    }

    operating_cash_flow_values = {
        "2023-09-30": 120.0,
        "2022-09-30": 110.0,
        "2021-09-30": 100.0,
        "2020-09-30": 90.0,
    }

    capex_values = {
        "2023-09-30": -20.0,
        "2022-09-30": -18.0,
        "2021-09-30": -15.0,
        "2020-09-30": -12.0,
    }

    free_cash_flow_values = {
        "2023-09-30": 100.0,
        "2022-09-30": 92.0,
        "2021-09-30": 85.0,
        "2020-09-30": 78.0,
    }

    total_assets_values = {
        "2023-09-30": 1000.0,
        "2022-09-30": 950.0,
        "2021-09-30": 900.0,
        "2020-09-30": 850.0,
    }

    total_liabilities_values = {
        "2023-09-30": 600.0,
        "2022-09-30": 570.0,
        "2021-09-30": 540.0,
        "2020-09-30": 510.0,
    }

    equity_values = {
        "2023-09-30": 400.0,
        "2022-09-30": 380.0,
        "2021-09-30": 360.0,
        "2020-09-30": 340.0,
    }

    for fiscal_date in annual_dates:
        rows.extend(
            [
                {
                    "source_symbol": "AAPL.US",
                    "statement_type": "income_statement",
                    "raw_period_type": "yearly",
                    "period_type": "annual",
                    "fiscal_date": fiscal_date,
                    "currency": "USD",
                    "line_item": "totalRevenue",
                    "value_numeric": revenue_values[fiscal_date],
                },
                {
                    "source_symbol": "AAPL.US",
                    "statement_type": "income_statement",
                    "raw_period_type": "yearly",
                    "period_type": "annual",
                    "fiscal_date": fiscal_date,
                    "currency": "USD",
                    "line_item": "netIncome",
                    "value_numeric": net_income_values[fiscal_date],
                },
                {
                    "source_symbol": "AAPL.US",
                    "statement_type": "cash_flow",
                    "raw_period_type": "yearly",
                    "period_type": "annual",
                    "fiscal_date": fiscal_date,
                    "currency": "USD",
                    "line_item": "totalCashFromOperatingActivities",
                    "value_numeric": operating_cash_flow_values[fiscal_date],
                },
                {
                    "source_symbol": "AAPL.US",
                    "statement_type": "cash_flow",
                    "raw_period_type": "yearly",
                    "period_type": "annual",
                    "fiscal_date": fiscal_date,
                    "currency": "USD",
                    "line_item": "capitalExpenditures",
                    "value_numeric": capex_values[fiscal_date],
                },
                {
                    "source_symbol": "AAPL.US",
                    "statement_type": "cash_flow",
                    "raw_period_type": "yearly",
                    "period_type": "annual",
                    "fiscal_date": fiscal_date,
                    "currency": "USD",
                    "line_item": "freeCashFlow",
                    "value_numeric": free_cash_flow_values[fiscal_date],
                },
                {
                    "source_symbol": "AAPL.US",
                    "statement_type": "balance_sheet",
                    "raw_period_type": "yearly",
                    "period_type": "annual",
                    "fiscal_date": fiscal_date,
                    "currency": "USD",
                    "line_item": "totalAssets",
                    "value_numeric": total_assets_values[fiscal_date],
                },
                {
                    "source_symbol": "AAPL.US",
                    "statement_type": "balance_sheet",
                    "raw_period_type": "yearly",
                    "period_type": "annual",
                    "fiscal_date": fiscal_date,
                    "currency": "USD",
                    "line_item": "totalLiab",
                    "value_numeric": total_liabilities_values[fiscal_date],
                },
                {
                    "source_symbol": "AAPL.US",
                    "statement_type": "balance_sheet",
                    "raw_period_type": "yearly",
                    "period_type": "annual",
                    "fiscal_date": fiscal_date,
                    "currency": "USD",
                    "line_item": "totalStockholderEquity",
                    "value_numeric": equity_values[fiscal_date],
                },
            ]
        )

    rows.append(
        {
            "source_symbol": "AAPL.US",
            "statement_type": "income_statement",
            "raw_period_type": "quarterly",
            "period_type": "quarterly",
            "fiscal_date": "2023-06-30",
            "currency": "USD",
            "line_item": "totalRevenue",
            "value_numeric": 90.0,
        }
    )

    return pd.DataFrame(rows)


def test_is_missing_detects_missing_values():
    assert is_missing(None)
    assert is_missing("")
    assert is_missing("   ")
    assert is_missing(float("nan"))
    assert not is_missing("AAPL")
    assert not is_missing(0)


def test_safe_float_converts_valid_values():
    assert safe_float("10.5") == 10.5
    assert safe_float(42) == 42.0
    assert safe_float(None) is None
    assert safe_float("not_a_number") is None


def test_safe_divide_handles_valid_and_invalid_values():
    assert safe_divide(10, 2) == 5.0
    assert safe_divide(10, 0) is None
    assert safe_divide(None, 2) is None
    assert safe_divide(10, None) is None


def test_calculate_growth():
    assert round(calculate_growth(120, 100), 4) == 0.2
    assert calculate_growth(120, 0) is None
    assert calculate_growth(None, 100) is None


def test_calculate_cagr():
    result = calculate_cagr(400, 300, periods=3)

    assert result is not None
    assert round(result, 4) == round((400 / 300) ** (1 / 3) - 1, 4)
    assert calculate_cagr(400, 0, periods=3) is None
    assert calculate_cagr(-400, 300, periods=3) is None


def test_filter_annual_rows_keeps_annual_and_yearly_rows():
    df = sample_statement_lines()

    result = filter_annual_rows(df)

    assert not result.empty
    assert "quarterly" not in set(result["period_type"])
    assert set(result["raw_period_type"]) == {"yearly"}


def test_get_recent_fiscal_dates_returns_latest_first():
    df = filter_annual_rows(sample_statement_lines())

    result = get_recent_fiscal_dates(df, max_dates=4)

    assert result == [
        "2023-09-30",
        "2022-09-30",
        "2021-09-30",
        "2020-09-30",
    ]


def test_get_line_item_value_returns_value():
    df = filter_annual_rows(sample_statement_lines())

    result = get_line_item_value(
        df=df,
        statement_type="income_statement",
        fiscal_date="2023-09-30",
        line_item="totalRevenue",
    )

    assert result == 400.0


def test_get_line_item_value_returns_none_for_missing():
    df = filter_annual_rows(sample_statement_lines())

    result = get_line_item_value(
        df=df,
        statement_type="income_statement",
        fiscal_date="2023-09-30",
        line_item="missingLineItem",
    )

    assert result is None


def test_count_positive_values():
    assert count_positive_values([1, 2, -1, 0, None]) == 2


def test_choose_free_cash_flow_prefers_reported_fcf():
    value, source = choose_free_cash_flow(
        operating_cash_flow=120.0,
        capital_expenditures=-20.0,
        reported_free_cash_flow=101.0,
    )

    assert value == 101.0
    assert source == "reported_freeCashFlow"


def test_choose_free_cash_flow_computes_from_negative_capex():
    value, source = choose_free_cash_flow(
        operating_cash_flow=120.0,
        capital_expenditures=-20.0,
        reported_free_cash_flow=None,
    )

    assert value == 100.0
    assert source == "computed_ocf_plus_negative_capex"


def test_choose_free_cash_flow_computes_from_positive_capex():
    value, source = choose_free_cash_flow(
        operating_cash_flow=120.0,
        capital_expenditures=20.0,
        reported_free_cash_flow=None,
    )

    assert value == 100.0
    assert source == "computed_ocf_minus_positive_capex"


def test_summarize_one_symbol_creates_scoring_ready_metrics():
    df = sample_statement_lines()

    summary = summarize_one_symbol(df)

    assert summary["source_symbol"] == "AAPL.US"
    assert summary["currency"] == "USD"
    assert summary["annual_period_count"] == 4
    assert summary["latest_fiscal_date"] == "2023-09-30"
    assert summary["prior_fiscal_date"] == "2022-09-30"

    assert summary["latest_revenue"] == 400.0
    assert summary["prior_revenue"] == 360.0
    assert round(summary["revenue_growth_yoy"], 4) == round((400 / 360) - 1, 4)
    assert summary["revenue_positive_year_count"] == 4

    assert summary["latest_net_income"] == 100.0
    assert summary["prior_net_income"] == 90.0
    assert summary["net_income_positive_year_count"] == 4

    assert summary["latest_operating_cash_flow"] == 120.0
    assert summary["latest_capex"] == -20.0
    assert summary["latest_reported_free_cash_flow"] == 100.0
    assert summary["latest_free_cash_flow"] == 100.0
    assert summary["free_cash_flow_source"] == "reported_freeCashFlow"
    assert summary["free_cash_flow_positive_year_count"] == 4

    assert summary["latest_net_margin"] == 0.25
    assert summary["latest_fcf_margin"] == 0.25
    assert summary["latest_total_assets"] == 1000.0
    assert summary["latest_total_liabilities"] == 600.0
    assert summary["latest_total_equity"] == 400.0
    assert summary["latest_total_equity_source"] == "totalStockholderEquity"
    assert summary["latest_liabilities_to_assets"] == 0.6
    assert summary["latest_debt_to_equity"] == 1.5
    assert summary["summary_quality_flags"] == ""


def test_summarize_one_symbol_flags_insufficient_coverage():
    df = sample_statement_lines()
    df = df[df["fiscal_date"].isin(["2023-09-30", "2022-09-30"])]

    summary = summarize_one_symbol(df)

    assert "insufficient_annual_coverage_lt_3" in summary["summary_quality_flags"]


def test_summarize_one_symbol_computes_equity_if_missing():
    df = sample_statement_lines()
    df = df[df["line_item"] != "totalStockholderEquity"]

    summary = summarize_one_symbol(df)

    assert summary["latest_total_equity"] == 400.0
    assert summary["latest_total_equity_source"] == "computed_assets_minus_liabilities"


def test_summarize_one_symbol_raises_error_for_empty_input():
    with pytest.raises(ValueError):
        summarize_one_symbol(pd.DataFrame())


def test_summarize_all_symbols_returns_one_row_per_symbol():
    df = sample_statement_lines()

    second = df.copy()
    second["source_symbol"] = "MSFT.US"

    combined = pd.concat([df, second], ignore_index=True)

    summary = summarize_all_symbols(combined)

    assert isinstance(summary, pd.DataFrame)
    assert len(summary) == 2
    assert set(summary["source_symbol"]) == {"AAPL.US", "MSFT.US"}


def test_summarize_all_symbols_handles_empty_input():
    result = summarize_all_symbols(pd.DataFrame())

    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_summarize_all_symbols_requires_source_symbol_column():
    df = sample_statement_lines().drop(columns=["source_symbol"])

    with pytest.raises(ValueError):
        summarize_all_symbols(df)