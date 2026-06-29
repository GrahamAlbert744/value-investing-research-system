"""
Build scoring-ready financial statement summary metrics.

Input:
- long-format financial statement lines

Output:
- one row per source_symbol with recent yearly statement metrics

This module intentionally stays simple:
- use yearly statements first
- calculate latest and prior-period values
- calculate basic growth and margin metrics
- preserve missing values instead of forcing fake estimates
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    """Safely divide two values, returning None when invalid."""
    try:
        numerator_float = float(numerator)
        denominator_float = float(denominator)
    except (TypeError, ValueError):
        return None

    if denominator_float == 0:
        return None

    return numerator_float / denominator_float


def get_line_item_value(
    df: pd.DataFrame,
    statement_type: str,
    period_type: str,
    fiscal_date: str,
    line_item: str,
) -> float | None:
    """Return one numeric statement value for a specific statement/date/item."""
    subset = df[
        (df["statement_type"] == statement_type)
        & (df["period_type"] == period_type)
        & (df["fiscal_date"] == fiscal_date)
        & (df["line_item"] == line_item)
    ]

    if subset.empty:
        return None

    value = subset.iloc[0].get("value_numeric")

    if pd.isna(value):
        return None

    return float(value)


def get_recent_fiscal_dates(
    df: pd.DataFrame,
    period_type: str = "yearly",
    max_dates: int = 2,
) -> list[str]:
    """Return most recent fiscal dates for one symbol and period type."""
    dates = (
        df[df["period_type"] == period_type]["fiscal_date"]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .sort_values(ascending=False)
        .tolist()
    )

    return dates[:max_dates]


def summarize_one_symbol(statement_lines: pd.DataFrame) -> dict[str, Any]:
    """Create one scoring-ready summary row for a single source symbol."""
    if statement_lines.empty:
        raise ValueError("statement_lines cannot be empty.")

    source_symbol = statement_lines["source_symbol"].iloc[0]
    currency = statement_lines["currency"].dropna().iloc[0] if statement_lines["currency"].notna().any() else None

    recent_dates = get_recent_fiscal_dates(
        df=statement_lines,
        period_type="yearly",
        max_dates=2,
    )

    latest_fiscal_date = recent_dates[0] if len(recent_dates) >= 1 else None
    prior_fiscal_date = recent_dates[1] if len(recent_dates) >= 2 else None

    latest_revenue = None
    prior_revenue = None
    latest_net_income = None
    prior_net_income = None
    latest_operating_cash_flow = None
    latest_capex = None
    latest_reported_fcf = None
    latest_total_assets = None
    latest_total_liabilities = None

    if latest_fiscal_date:
        latest_revenue = get_line_item_value(
            statement_lines,
            "income_statement",
            "yearly",
            latest_fiscal_date,
            "totalRevenue",
        )
        latest_net_income = get_line_item_value(
            statement_lines,
            "income_statement",
            "yearly",
            latest_fiscal_date,
            "netIncome",
        )
        latest_operating_cash_flow = get_line_item_value(
            statement_lines,
            "cash_flow",
            "yearly",
            latest_fiscal_date,
            "totalCashFromOperatingActivities",
        )
        latest_capex = get_line_item_value(
            statement_lines,
            "cash_flow",
            "yearly",
            latest_fiscal_date,
            "capitalExpenditures",
        )
        latest_reported_fcf = get_line_item_value(
            statement_lines,
            "cash_flow",
            "yearly",
            latest_fiscal_date,
            "freeCashFlow",
        )
        latest_total_assets = get_line_item_value(
            statement_lines,
            "balance_sheet",
            "yearly",
            latest_fiscal_date,
            "totalAssets",
        )
        latest_total_liabilities = get_line_item_value(
            statement_lines,
            "balance_sheet",
            "yearly",
            latest_fiscal_date,
            "totalLiab",
        )

    if prior_fiscal_date:
        prior_revenue = get_line_item_value(
            statement_lines,
            "income_statement",
            "yearly",
            prior_fiscal_date,
            "totalRevenue",
        )
        prior_net_income = get_line_item_value(
            statement_lines,
            "income_statement",
            "yearly",
            prior_fiscal_date,
            "netIncome",
        )

    if latest_reported_fcf is not None:
        latest_free_cash_flow = latest_reported_fcf
        fcf_source = "reported"
    elif latest_operating_cash_flow is not None and latest_capex is not None:
        latest_free_cash_flow = latest_operating_cash_flow + latest_capex
        fcf_source = "computed_operating_cash_flow_plus_capex"
    else:
        latest_free_cash_flow = None
        fcf_source = "missing"

    latest_equity_estimate = None
    if latest_total_assets is not None and latest_total_liabilities is not None:
        latest_equity_estimate = latest_total_assets - latest_total_liabilities

    return {
        "source_symbol": source_symbol,
        "currency": currency,
        "latest_yearly_fiscal_date": latest_fiscal_date,
        "prior_yearly_fiscal_date": prior_fiscal_date,
        "yearly_periods_available": len(
            statement_lines[statement_lines["period_type"] == "yearly"]["fiscal_date"]
            .dropna()
            .drop_duplicates()
        ),
        "latest_revenue": latest_revenue,
        "prior_revenue": prior_revenue,
        "revenue_growth_yoy": safe_divide(
            latest_revenue - prior_revenue
            if latest_revenue is not None and prior_revenue is not None
            else None,
            prior_revenue,
        ),
        "latest_net_income": latest_net_income,
        "prior_net_income": prior_net_income,
        "net_income_growth_yoy": safe_divide(
            latest_net_income - prior_net_income
            if latest_net_income is not None and prior_net_income is not None
            else None,
            prior_net_income,
        ),
        "latest_net_margin": safe_divide(latest_net_income, latest_revenue),
        "latest_operating_cash_flow": latest_operating_cash_flow,
        "latest_capital_expenditures": latest_capex,
        "latest_free_cash_flow": latest_free_cash_flow,
        "free_cash_flow_source": fcf_source,
        "latest_fcf_margin": safe_divide(latest_free_cash_flow, latest_revenue),
        "latest_total_assets": latest_total_assets,
        "latest_total_liabilities": latest_total_liabilities,
        "latest_equity_estimate": latest_equity_estimate,
        "latest_liabilities_to_assets": safe_divide(
            latest_total_liabilities,
            latest_total_assets,
        ),
    }


def build_financial_statement_summary(statement_lines: pd.DataFrame) -> pd.DataFrame:
    """Build one financial statement summary row per source symbol."""
    if statement_lines.empty:
        return pd.DataFrame()

    required_columns = {
        "source_symbol",
        "statement_type",
        "period_type",
        "fiscal_date",
        "line_item",
        "value_numeric",
    }

    missing_columns = required_columns - set(statement_lines.columns)

    if missing_columns:
        raise ValueError(
            "statement_lines is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    rows = []

    for source_symbol, symbol_df in statement_lines.groupby("source_symbol"):
        rows.append(summarize_one_symbol(symbol_df.copy()))

    return pd.DataFrame(rows).sort_values(by=["source_symbol"])