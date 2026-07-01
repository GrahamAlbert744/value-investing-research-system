"""
Financial statement extraction utilities for EODHD fundamentals JSON.

This module converts nested EODHD financial statement data into long-format rows.

C4 metadata upgrades:
- preserve raw_period_type
- add standardized period_type
- add raw_value_type
- add statement_currency_source
- add quality_flags
- prefer requested/source symbol over inferred symbol
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
    Infer ticker from EODHD General section.

    This is a fallback only. Prefer passing source_symbol from the requested ticker
    or raw file name so joins remain stable.
    """
    general = data.get("General", {})

    if not isinstance(general, dict):
        return "UNKNOWN"

    primary_ticker = general.get("PrimaryTicker")
    if primary_ticker:
        return str(primary_ticker).upper()

    code = general.get("Code")
    exchange = general.get("Exchange")

    if code and exchange:
        return f"{str(code).upper()}.{str(exchange).upper()}"

    if code:
        return str(code).upper()

    return "UNKNOWN"


def standardize_period_type(raw_period_type: str, config: dict[str, Any]) -> str:
    """Convert EODHD raw period type to project-standard period type."""
    period_config = config.get("period_types", {})

    if isinstance(period_config, dict):
        period_spec = period_config.get(raw_period_type, {})
        if isinstance(period_spec, dict):
            return period_spec.get("standard_period_type", raw_period_type)

    if raw_period_type == "yearly":
        return "annual"

    return raw_period_type


def safe_numeric(value: Any) -> float | None:
    """Convert value to numeric when possible; otherwise return None."""
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def infer_raw_value_type(value: Any) -> str:
    """Return a simple raw value type label."""
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "bool"

    if isinstance(value, int):
        return "int"

    if isinstance(value, float):
        return "float"

    if isinstance(value, str):
        return "str"

    return type(value).__name__


def build_quality_flags(
    line_item: str,
    value: Any,
    value_numeric: float | None,
    line_items: dict[str, Any],
) -> str:
    """Build simple quality flags for one financial statement line."""
    flags: list[str] = []

    if value_numeric is None and line_item not in {"date", "filing_date", "currency_symbol"}:
        flags.append("missing_or_non_numeric_value")

    if line_item in {"totalRevenue", "revenue"} and value_numeric is not None and value_numeric < 0:
        flags.append("negative_revenue")

    if line_item in {"totalAssets"} and value_numeric is not None and value_numeric < 0:
        flags.append("negative_assets")

    if "filing_date" not in line_items or line_items.get("filing_date") in {None, ""}:
        flags.append("missing_filing_date")

    return ";".join(flags)


def get_period_type_keys(config: dict[str, Any]) -> list[str]:
    """Return raw period type keys from config."""
    period_types = config.get("period_types", ["yearly", "quarterly"])

    if isinstance(period_types, dict):
        return list(period_types.keys())

    return list(period_types)


def extract_statement_lines(
    data: dict[str, Any],
    config: dict[str, Any],
    source_symbol: str | None = None,
) -> pd.DataFrame:
    """
    Extract financial statement line items from EODHD fundamentals JSON.

    Returns one row per:
    source_symbol + statement_type + raw_period_type + fiscal_date + line_item
    """
    if source_symbol is None:
        source_symbol = infer_source_symbol_from_fundamentals(data)

    statement_sections = config.get("statement_sections", {})
    raw_period_types = get_period_type_keys(config)

    extracted_at_utc = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []

    for statement_type, statement_spec in statement_sections.items():
        raw_path = statement_spec["raw_path"]
        statement_data = get_nested_value(data, raw_path)

        if not isinstance(statement_data, dict):
            continue

        statement_currency = statement_data.get("currency_symbol")
        statement_currency_source = (
            f"{raw_path}.currency_symbol" if statement_currency else ""
        )

        for raw_period_type in raw_period_types:
            period_data = statement_data.get(raw_period_type)
            standard_period_type = standardize_period_type(
                raw_period_type=raw_period_type,
                config=config,
            )

            if not isinstance(period_data, dict):
                continue

            for fiscal_date, line_items in period_data.items():
                if not isinstance(line_items, dict):
                    continue

                filing_date = line_items.get("filing_date")
                reported_date = line_items.get("date", fiscal_date)

                for line_item, value in line_items.items():
                    value_numeric = safe_numeric(value)

                    rows.append(
                        {
                            "source_symbol": source_symbol,
                            "statement_type": statement_type,
                            "raw_period_type": raw_period_type,
                            "period_type": standard_period_type,
                            "fiscal_date": fiscal_date,
                            "reported_date": reported_date,
                            "filing_date": filing_date,
                            "currency": statement_currency,
                            "statement_currency_source": statement_currency_source,
                            "line_item": line_item,
                            "value": value,
                            "value_numeric": value_numeric,
                            "raw_value_type": infer_raw_value_type(value),
                            "quality_flags": build_quality_flags(
                                line_item=line_item,
                                value=value,
                                value_numeric=value_numeric,
                                line_items=line_items,
                            ),
                            "source_path": (
                                f"{raw_path}.{raw_period_type}."
                                f"{fiscal_date}.{line_item}"
                            ),
                            "extracted_at_utc": extracted_at_utc,
                        }
                    )

    return pd.DataFrame(rows)


def build_financial_statement_coverage(statement_lines: pd.DataFrame) -> pd.DataFrame:
    """Build coverage summary from extracted financial statement lines."""
    if statement_lines.empty:
        return pd.DataFrame(
            columns=[
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
        )

    coverage = (
        statement_lines.groupby(
            ["source_symbol", "statement_type", "raw_period_type", "period_type"],
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
        by=["source_symbol", "statement_type", "period_type"],
        ascending=True,
    )