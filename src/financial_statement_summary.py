"""
Build scoring-ready financial statement summary metrics.

Input:
- outputs/financial_statement_lines.csv

Output:
- one row per source_symbol with recent annual financial metrics

C5 upgrades:
- supports C4 schema where raw_period_type='yearly' and period_type='annual'
- keeps backward compatibility with older period_type='yearly'
- adds multi-year growth, positive-year counts, margins, leverage, and quality flags
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


ANNUAL_PERIOD_LABELS = {"annual", "yearly"}
YEARLY_RAW_PERIOD_LABELS = {"yearly"}


def is_missing(value: Any) -> bool:
    """Return True when value should be treated as missing."""
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


def safe_divide(numerator: Any, denominator: Any) -> float | None:
    """Safely divide two values, returning None when invalid."""
    numerator_float = safe_float(numerator)
    denominator_float = safe_float(denominator)

    if numerator_float is None or denominator_float is None:
        return None

    if denominator_float == 0:
        return None

    return numerator_float / denominator_float


def calculate_growth(current_value: Any, prior_value: Any) -> float | None:
    """Calculate one-period growth."""
    current_float = safe_float(current_value)
    prior_float = safe_float(prior_value)

    if current_float is None or prior_float is None:
        return None

    if prior_float == 0:
        return None

    return (current_float / prior_float) - 1.0


def calculate_cagr(current_value: Any, old_value: Any, periods: int) -> float | None:
    """Calculate compound annual growth rate."""
    current_float = safe_float(current_value)
    old_float = safe_float(old_value)

    if current_float is None or old_float is None:
        return None

    if current_float <= 0 or old_float <= 0 or periods <= 0:
        return None

    return (current_float / old_float) ** (1.0 / periods) - 1.0


def filter_annual_rows(statement_lines: pd.DataFrame) -> pd.DataFrame:
    """
    Return annual rows.

    C4 schema:
    - raw_period_type = yearly
    - period_type = annual

    Older schema:
    - period_type = yearly
    """
    if statement_lines.empty:
        return statement_lines.copy()

    mask = pd.Series(False, index=statement_lines.index)

    if "period_type" in statement_lines.columns:
        mask = mask | statement_lines["period_type"].astype(str).str.lower().isin(
            ANNUAL_PERIOD_LABELS
        )

    if "raw_period_type" in statement_lines.columns:
        mask = mask | statement_lines["raw_period_type"].astype(str).str.lower().isin(
            YEARLY_RAW_PERIOD_LABELS
        )

    return statement_lines[mask].copy()


def get_recent_fiscal_dates(
    df: pd.DataFrame,
    max_dates: int = 4,
) -> list[str]:
    """Return most recent fiscal dates from annual statement rows."""
    if df.empty or "fiscal_date" not in df.columns:
        return []

    dates = (
        df["fiscal_date"]
        .dropna()
        .astype(str)
        .drop_duplicates()
        .sort_values(ascending=False)
        .tolist()
    )

    return dates[:max_dates]


def get_line_item_value(
    df: pd.DataFrame,
    statement_type: str,
    fiscal_date: str,
    line_item: str,
) -> float | None:
    """Return one numeric statement value for a specific statement/date/item."""
    subset = df[
        (df["statement_type"] == statement_type)
        & (df["fiscal_date"].astype(str) == str(fiscal_date))
        & (df["line_item"] == line_item)
    ]

    if subset.empty:
        return None

    value = subset.iloc[0].get("value_numeric")

    return safe_float(value)


def get_first_available_line_item_value(
    df: pd.DataFrame,
    statement_type: str,
    fiscal_date: str,
    candidate_line_items: list[str],
) -> tuple[float | None, str | None]:
    """Return the first available numeric line-item value."""
    for line_item in candidate_line_items:
        value = get_line_item_value(
            df=df,
            statement_type=statement_type,
            fiscal_date=fiscal_date,
            line_item=line_item,
        )

        if value is not None:
            return value, line_item

    return None, None


def count_positive_values(values: list[float | None]) -> int:
    """Count positive numeric values."""
    return sum(value is not None and value > 0 for value in values)


def choose_free_cash_flow(
    operating_cash_flow: float | None,
    capital_expenditures: float | None,
    reported_free_cash_flow: float | None,
) -> tuple[float | None, str]:
    """
    Choose free cash flow.

    Prefer reported freeCashFlow when available.
    Otherwise compute from operating cash flow and capex.

    EODHD capex is commonly negative, so:
    - if capex is negative, computed FCF = OCF + capex
    - if capex is positive, computed FCF = OCF - capex
    """
    if reported_free_cash_flow is not None:
        return reported_free_cash_flow, "reported_freeCashFlow"

    if operating_cash_flow is None or capital_expenditures is None:
        return None, "missing"

    if capital_expenditures < 0:
        return operating_cash_flow + capital_expenditures, "computed_ocf_plus_negative_capex"

    return operating_cash_flow - capital_expenditures, "computed_ocf_minus_positive_capex"


def summarize_one_symbol(statement_lines: pd.DataFrame) -> dict[str, Any]:
    """Create one scoring-ready summary row for one source symbol."""
    if statement_lines.empty:
        raise ValueError("statement_lines cannot be empty.")

    source_symbol = statement_lines["source_symbol"].iloc[0]

    currency = None
    if "currency" in statement_lines.columns and statement_lines["currency"].notna().any():
        currency = statement_lines["currency"].dropna().iloc[0]

    annual_lines = filter_annual_rows(statement_lines)
    recent_dates = get_recent_fiscal_dates(annual_lines, max_dates=4)

    latest_fiscal_date = recent_dates[0] if len(recent_dates) >= 1 else None
    prior_fiscal_date = recent_dates[1] if len(recent_dates) >= 2 else None
    third_fiscal_date = recent_dates[2] if len(recent_dates) >= 3 else None
    fourth_fiscal_date = recent_dates[3] if len(recent_dates) >= 4 else None

    summary: dict[str, Any] = {
        "source_symbol": source_symbol,
        "summary_built_at_utc": datetime.now(timezone.utc).isoformat(),
        "currency": currency,
        "annual_period_count": len(recent_dates),
        "latest_fiscal_date": latest_fiscal_date,
        "prior_fiscal_date": prior_fiscal_date,
        "third_fiscal_date": third_fiscal_date,
        "fourth_fiscal_date": fourth_fiscal_date,
    }

    statement_period_counts = {}
    for statement_type in ["income_statement", "balance_sheet", "cash_flow"]:
        statement_period_counts[statement_type] = (
            annual_lines[annual_lines["statement_type"] == statement_type]["fiscal_date"]
            .dropna()
            .astype(str)
            .nunique()
        )

    summary.update(
        {
            "annual_income_statement_period_count": statement_period_counts["income_statement"],
            "annual_balance_sheet_period_count": statement_period_counts["balance_sheet"],
            "annual_cash_flow_period_count": statement_period_counts["cash_flow"],
        }
    )

    revenue_values: list[float | None] = []
    net_income_values: list[float | None] = []
    fcf_values: list[float | None] = []

    for fiscal_date in recent_dates:
        revenue_values.append(
            get_line_item_value(
                df=annual_lines,
                statement_type="income_statement",
                fiscal_date=fiscal_date,
                line_item="totalRevenue",
            )
        )

        net_income_values.append(
            get_line_item_value(
                df=annual_lines,
                statement_type="income_statement",
                fiscal_date=fiscal_date,
                line_item="netIncome",
            )
        )

        operating_cash_flow = get_line_item_value(
            df=annual_lines,
            statement_type="cash_flow",
            fiscal_date=fiscal_date,
            line_item="totalCashFromOperatingActivities",
        )
        capital_expenditures = get_line_item_value(
            df=annual_lines,
            statement_type="cash_flow",
            fiscal_date=fiscal_date,
            line_item="capitalExpenditures",
        )
        reported_free_cash_flow = get_line_item_value(
            df=annual_lines,
            statement_type="cash_flow",
            fiscal_date=fiscal_date,
            line_item="freeCashFlow",
        )

        fcf_value, _ = choose_free_cash_flow(
            operating_cash_flow=operating_cash_flow,
            capital_expenditures=capital_expenditures,
            reported_free_cash_flow=reported_free_cash_flow,
        )
        fcf_values.append(fcf_value)

    latest_revenue = revenue_values[0] if len(revenue_values) >= 1 else None
    prior_revenue = revenue_values[1] if len(revenue_values) >= 2 else None
    fourth_revenue = revenue_values[3] if len(revenue_values) >= 4 else None

    latest_net_income = net_income_values[0] if len(net_income_values) >= 1 else None
    prior_net_income = net_income_values[1] if len(net_income_values) >= 2 else None
    fourth_net_income = net_income_values[3] if len(net_income_values) >= 4 else None

    latest_free_cash_flow = fcf_values[0] if len(fcf_values) >= 1 else None
    prior_free_cash_flow = fcf_values[1] if len(fcf_values) >= 2 else None
    fourth_free_cash_flow = fcf_values[3] if len(fcf_values) >= 4 else None

    latest_operating_cash_flow = None
    latest_capex = None
    latest_reported_fcf = None
    free_cash_flow_source = "missing"

    latest_total_assets = None
    latest_total_liabilities = None
    latest_total_equity = None
    latest_total_equity_source = None

    if latest_fiscal_date:
        latest_operating_cash_flow = get_line_item_value(
            df=annual_lines,
            statement_type="cash_flow",
            fiscal_date=latest_fiscal_date,
            line_item="totalCashFromOperatingActivities",
        )
        latest_capex = get_line_item_value(
            df=annual_lines,
            statement_type="cash_flow",
            fiscal_date=latest_fiscal_date,
            line_item="capitalExpenditures",
        )
        latest_reported_fcf = get_line_item_value(
            df=annual_lines,
            statement_type="cash_flow",
            fiscal_date=latest_fiscal_date,
            line_item="freeCashFlow",
        )

        latest_free_cash_flow, free_cash_flow_source = choose_free_cash_flow(
            operating_cash_flow=latest_operating_cash_flow,
            capital_expenditures=latest_capex,
            reported_free_cash_flow=latest_reported_fcf,
        )

        latest_total_assets = get_line_item_value(
            df=annual_lines,
            statement_type="balance_sheet",
            fiscal_date=latest_fiscal_date,
            line_item="totalAssets",
        )
        latest_total_liabilities = get_line_item_value(
            df=annual_lines,
            statement_type="balance_sheet",
            fiscal_date=latest_fiscal_date,
            line_item="totalLiab",
        )

        latest_total_equity, latest_total_equity_source = (
            get_first_available_line_item_value(
                df=annual_lines,
                statement_type="balance_sheet",
                fiscal_date=latest_fiscal_date,
                candidate_line_items=[
                    "totalStockholderEquity",
                    "totalStockholdersEquity",
                    "totalShareholderEquity",
                    "totalEquity",
                ],
            )
        )

        if latest_total_equity is None and latest_total_assets is not None and latest_total_liabilities is not None:
            latest_total_equity = latest_total_assets - latest_total_liabilities
            latest_total_equity_source = "computed_assets_minus_liabilities"

    revenue_growth_yoy = calculate_growth(latest_revenue, prior_revenue)
    net_income_growth_yoy = calculate_growth(latest_net_income, prior_net_income)
    free_cash_flow_growth_yoy = calculate_growth(latest_free_cash_flow, prior_free_cash_flow)

    revenue_3yr_cagr = calculate_cagr(latest_revenue, fourth_revenue, periods=3)
    net_income_3yr_cagr = calculate_cagr(latest_net_income, fourth_net_income, periods=3)
    free_cash_flow_3yr_cagr = calculate_cagr(
        latest_free_cash_flow,
        fourth_free_cash_flow,
        periods=3,
    )

    latest_net_margin = safe_divide(latest_net_income, latest_revenue)
    latest_fcf_margin = safe_divide(latest_free_cash_flow, latest_revenue)
    latest_liabilities_to_assets = safe_divide(latest_total_liabilities, latest_total_assets)

    latest_debt_to_equity = safe_divide(latest_total_liabilities, latest_total_equity)

    summary_quality_flags: list[str] = []

    if len(recent_dates) < 3:
        summary_quality_flags.append("insufficient_annual_coverage_lt_3")

    if statement_period_counts["income_statement"] < 3:
        summary_quality_flags.append("income_statement_annual_coverage_lt_3")

    if statement_period_counts["balance_sheet"] < 3:
        summary_quality_flags.append("balance_sheet_annual_coverage_lt_3")

    if statement_period_counts["cash_flow"] < 3:
        summary_quality_flags.append("cash_flow_annual_coverage_lt_3")

    if latest_revenue is None:
        summary_quality_flags.append("missing_latest_revenue")

    if latest_net_income is None:
        summary_quality_flags.append("missing_latest_net_income")

    if latest_free_cash_flow is None:
        summary_quality_flags.append("missing_latest_free_cash_flow")

    if latest_total_assets is None:
        summary_quality_flags.append("missing_latest_total_assets")

    if latest_total_liabilities is None:
        summary_quality_flags.append("missing_latest_total_liabilities")

    if latest_total_equity is not None and latest_total_equity < 0:
        summary_quality_flags.append("negative_equity")

    summary.update(
        {
            "latest_revenue": latest_revenue,
            "prior_revenue": prior_revenue,
            "revenue_growth_yoy": revenue_growth_yoy,
            "revenue_3yr_cagr": revenue_3yr_cagr,
            "revenue_positive_year_count": count_positive_values(revenue_values),
            "latest_net_income": latest_net_income,
            "prior_net_income": prior_net_income,
            "net_income_growth_yoy": net_income_growth_yoy,
            "net_income_3yr_cagr": net_income_3yr_cagr,
            "net_income_positive_year_count": count_positive_values(net_income_values),
            "latest_operating_cash_flow": latest_operating_cash_flow,
            "latest_capex": latest_capex,
            "latest_reported_free_cash_flow": latest_reported_fcf,
            "latest_free_cash_flow": latest_free_cash_flow,
            "prior_free_cash_flow": prior_free_cash_flow,
            "free_cash_flow_growth_yoy": free_cash_flow_growth_yoy,
            "free_cash_flow_3yr_cagr": free_cash_flow_3yr_cagr,
            "free_cash_flow_positive_year_count": count_positive_values(fcf_values),
            "free_cash_flow_source": free_cash_flow_source,
            "latest_net_margin": latest_net_margin,
            "latest_fcf_margin": latest_fcf_margin,
            "latest_total_assets": latest_total_assets,
            "latest_total_liabilities": latest_total_liabilities,
            "latest_total_equity": latest_total_equity,
            "latest_total_equity_source": latest_total_equity_source,
            "latest_liabilities_to_assets": latest_liabilities_to_assets,
            "latest_debt_to_equity": latest_debt_to_equity,
            "summary_quality_flags": ";".join(summary_quality_flags),
        }
    )

    return summary


def summarize_all_symbols(statement_lines: pd.DataFrame) -> pd.DataFrame:
    """Summarize financial statements for all source symbols."""
    if statement_lines.empty:
        return pd.DataFrame()

    if "source_symbol" not in statement_lines.columns:
        raise ValueError("statement_lines must include source_symbol.")

    rows = []

    for source_symbol, group in statement_lines.groupby("source_symbol", dropna=False):
        if is_missing(source_symbol):
            continue

        rows.append(summarize_one_symbol(group.copy()))

    summary = pd.DataFrame(rows)

    if summary.empty:
        return summary

    return summary.sort_values("source_symbol").reset_index(drop=True)