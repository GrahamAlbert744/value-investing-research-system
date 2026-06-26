"""
Financial statement extraction utilities for EODHD fundamentals JSON.

This module converts nested EODHD financial statement data into long-format rows:

ticker | statement_type | period_type | fiscal_date | line_item | value | currency | source_path

The goal is to preserve raw accounting line items before scoring or valuation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_financial_statement_config(config_path: Path) -> dict[str, Any]:
    """Load financial statement extraction config."""
    if not config_path.exists():
        raise FileNotFoundError(f"Financial statement config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise TypeError("Financial statement config must load as a dictionary.")

    return config


def get_nested_value(data: dict[str, Any], raw_path: str) -> Any:
    """Get a nested value from a dictionary using a dot-separated path."""
    current: Any = data

    for part in raw_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


def infer_source_symbol_from_fundamentals(data: dict[str, Any]) -> str:
    """
    Infer canonical ticker from EODHD General section.

    Falls back to UNKNOWN if Code/Exchange are unavailable.
    """
    general = data.get("General", {})

    if not isinstance(general, dict):
        return "UNKNOWN"

    code = general.get("Code")
    exchange = general.get("Exchange")

    if code and exchange:
        return f"{str(code).upper()}.{str(exchange).upper()}"

    if code:
        return str(code).upper()

    return "UNKNOWN"


def safe_numeric(value: Any) -> float | None:
    """Convert value to numeric when possible; otherwise return None."""
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_statement_lines(
    data: dict[str, Any],
    config: dict[str, Any],
    source_symbol: str | None = None,
) -> pd.DataFrame:
    """
    Extract financial statement line items from EODHD fundamentals JSON.

    Returns one row per:
    ticker + statement_type + period_type + fiscal_date + line_item
    """
    if source_symbol is None:
        source_symbol = infer_source_symbol_from_fundamentals(data)

    statement_sections = config.get("statement_sections", {})
    period_types = config.get("period_types", ["yearly", "quarterly"])

    extracted_at_utc = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []

    for statement_type, statement_spec in statement_sections.items():
        raw_path = statement_spec["raw_path"]
        statement_data = get_nested_value(data, raw_path)

        if not isinstance(statement_data, dict):
            continue

        currency = statement_data.get("currency_symbol")

        for period_type in period_types:
            period_data = statement_data.get(period_type)

            if not isinstance(period_data, dict):
                continue

            for fiscal_date, line_items in period_data.items():
                if not isinstance(line_items, dict):
                    continue

                for line_item, value in line_items.items():
                    source_path = (
                        f"{raw_path}.{period_type}.{fiscal_date}.{line_item}"
                    )

                    rows.append(
                        {
                            "source_symbol": source_symbol,
                            "statement_type": statement_type,
                            "period_type": period_type,
                            "fiscal_date": fiscal_date,
                            "currency": currency,
                            "line_item": line_item,
                            "value": value,
                            "value_numeric": safe_numeric(value),
                            "source_path": source_path,
                            "extracted_at_utc": extracted_at_utc,
                        }
                    )

    return pd.DataFrame(rows)


def build_financial_statement_coverage(statement_lines: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize statement coverage by source symbol, statement type, and period type.
    """
    if statement_lines.empty:
        return pd.DataFrame(
            columns=[
                "source_symbol",
                "statement_type",
                "period_type",
                "period_count",
                "line_count",
                "latest_fiscal_date",
                "earliest_fiscal_date",
                "currency",
            ]
        )

    coverage = (
        statement_lines.groupby(
            ["source_symbol", "statement_type", "period_type"],
            dropna=False,
        )
        .agg(
            period_count=("fiscal_date", "nunique"),
            line_count=("line_item", "count"),
            latest_fiscal_date=("fiscal_date", "max"),
            earliest_fiscal_date=("fiscal_date", "min"),
            currency=("currency", "first"),
        )
        .reset_index()
    )

    return coverage.sort_values(
        by=["source_symbol", "statement_type", "period_type"]
    )