"""
Create a field audit from a raw EODHD fundamentals JSON response.

The audit flattens nested JSON into field paths so we can decide:
- which fields matter
- which fields should be normalized
- which fields are nested tables
- which fields may create data-quality issues
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def shorten_value(value: Any, max_length: int = 120) -> str:
    """Convert sample values to short readable strings."""
    if value is None:
        return ""

    value_text = str(value)

    if len(value_text) > max_length:
        return value_text[:max_length] + "..."

    return value_text


def infer_field_role(path: str) -> str:
    """Assign a rough first-pass field role based on path."""
    lower_path = path.lower()

    if lower_path.startswith("general"):
        return "identity_metadata"
    if lower_path.startswith("highlights"):
        return "summary_metrics"
    if lower_path.startswith("valuation"):
        return "valuation"
    if lower_path.startswith("financials"):
        return "financial_statement"
    if lower_path.startswith("earnings"):
        return "earnings"
    if lower_path.startswith("splitsdividends"):
        return "dividends_splits"
    if lower_path.startswith("analystratings"):
        return "analyst_ratings"
    if lower_path.startswith("technicals"):
        return "technical_market_data"
    if lower_path.startswith("holders"):
        return "ownership"
    if lower_path.startswith("insidertransactions"):
        return "insider_transactions"
    if lower_path.startswith("esgscores"):
        return "esg"
    if lower_path.startswith("outstandingshares"):
        return "shares"

    return "unknown"


def flatten_json(
    obj: Any,
    parent_path: str = "",
    rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Recursively flatten JSON into field-level audit rows.

    Lists are summarized rather than fully exploded to avoid giant audit files.
    """
    if rows is None:
        rows = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{parent_path}.{key}" if parent_path else key

            rows.append(
                {
                    "path": path,
                    "top_level_field": path.split(".")[0],
                    "depth": path.count(".") + 1,
                    "python_type": type(value).__name__,
                    "is_null": value is None,
                    "sample_value": shorten_value(value),
                    "field_role_guess": infer_field_role(path),
                }
            )

            flatten_json(value, path, rows)

    elif isinstance(obj, list):
        path = parent_path
        rows.append(
            {
                "path": f"{path}[]",
                "top_level_field": path.split(".")[0] if path else "",
                "depth": path.count(".") + 1 if path else 1,
                "python_type": "list",
                "is_null": False,
                "sample_value": f"list_length={len(obj)}",
                "field_role_guess": infer_field_role(path),
            }
        )

        if obj and isinstance(obj[0], dict):
            flatten_json(obj[0], f"{path}[]", rows)

    return rows


def create_field_audit(data: dict[str, Any]) -> pd.DataFrame:
    """Create a clean field audit DataFrame from EODHD fundamentals JSON."""
    rows = flatten_json(data)

    audit_df = pd.DataFrame(rows)

    if audit_df.empty:
        return audit_df

    audit_df = audit_df.drop_duplicates(subset=["path"]).sort_values(
        by=["top_level_field", "path"]
    )

    audit_df["keep_candidate"] = audit_df["field_role_guess"].isin(
        [
            "identity_metadata",
            "summary_metrics",
            "valuation",
            "financial_statement",
            "earnings",
            "dividends_splits",
            "shares",
        ]
    )

    return audit_df