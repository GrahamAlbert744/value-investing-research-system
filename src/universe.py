"""
Universe construction utilities.

This module builds a clean universe_master table from a manually curated
seed universe before we expand to API-driven exchange-wide universes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_universe_config(config_path: Path) -> dict[str, Any]:
    """Load universe construction config."""
    if not config_path.exists():
        raise FileNotFoundError(f"Universe config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise TypeError("Universe config must load as a dictionary.")

    return config


def load_seed_universe(seed_path: Path) -> pd.DataFrame:
    """Load seed universe CSV."""
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed universe file not found: {seed_path}")

    return pd.read_csv(seed_path)


def split_ticker(ticker: str) -> tuple[str, str | None]:
    """
    Split ticker into code and exchange suffix.

    Example:
    AAPL.US -> ("AAPL", "US")
    """
    if not isinstance(ticker, str) or ticker.strip() == "":
        return "", None

    parts = ticker.strip().split(".")

    if len(parts) == 2:
        return parts[0], parts[1]

    return ticker.strip(), None


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: list[str],
) -> list[str]:
    """Return missing required columns."""
    return [column for column in required_columns if column not in df.columns]


def normalize_include_flag(value: Any) -> bool:
    """Normalize include_in_mvp values to boolean."""
    if isinstance(value, bool):
        return value

    if value is None or pd.isna(value):
        return False

    return str(value).strip().lower() in {"yes", "true", "1", "y"}


def build_exclusion_reason(row: pd.Series, config: dict[str, Any]) -> str:
    """
    Apply simple keyword-based exclusion rules.

    This is intentionally conservative and transparent.
    """
    manual_reason = row.get("manual_exclusion_reason", "")

    if isinstance(manual_reason, str) and manual_reason.strip():
        return manual_reason.strip()

    text = " ".join(
        str(row.get(column, ""))
        for column in ["company_name", "sector", "industry", "notes"]
    ).lower()

    excluded_categories = config.get("excluded_categories", {})

    for category, rule in excluded_categories.items():
        keywords = rule.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in text:
                return f"excluded_category:{category}"

    return ""


def build_universe_master(
    seed_df: pd.DataFrame,
    config: dict[str, Any],
) -> pd.DataFrame:
    """Build normalized universe_master dataframe from seed universe."""
    required_columns = config.get("required_columns", [])
    missing_columns = validate_required_columns(seed_df, required_columns)

    if missing_columns:
        raise ValueError(
            "Seed universe is missing required columns: "
            + ", ".join(missing_columns)
        )

    df = seed_df.copy()

    ticker_parts = df["ticker"].apply(split_ticker)
    df["code"] = ticker_parts.apply(lambda value: value[0])
    df["parsed_exchange_suffix"] = ticker_parts.apply(lambda value: value[1])

    df["exchange_suffix"] = df["exchange_suffix"].fillna(df["parsed_exchange_suffix"])
    df["exchange_suffix"] = df["exchange_suffix"].astype(str).str.upper()

    allowed_suffixes = set(config.get("allowed_exchange_suffixes", []))
    df["exchange_allowed"] = df["exchange_suffix"].isin(allowed_suffixes)

    df["include_in_mvp"] = df["include_in_mvp"].apply(normalize_include_flag)
    df["exclusion_reason"] = df.apply(
        lambda row: build_exclusion_reason(row, config),
        axis=1,
    )

    df["passes_manual_filters"] = df["exclusion_reason"].eq("")
    df["include_in_universe"] = (
        df["include_in_mvp"] & df["exchange_allowed"] & df["passes_manual_filters"]
    )

    now = datetime.now(timezone.utc).isoformat()
    default_flags = config.get("default_flags", {})

    df["is_seed_universe"] = bool(default_flags.get("is_seed_universe", True))
    df["data_source"] = default_flags.get("data_source", "manual_seed")
    df["first_seen_at_utc"] = now
    df["last_updated_at_utc"] = now

    output_columns = [
        "ticker",
        "code",
        "exchange_suffix",
        "company_name",
        "sector",
        "industry",
        "country",
        "currency",
        "include_in_mvp",
        "exchange_allowed",
        "passes_manual_filters",
        "include_in_universe",
        "exclusion_reason",
        "is_seed_universe",
        "data_source",
        "first_seen_at_utc",
        "last_updated_at_utc",
        "notes",
    ]

    return df[output_columns].sort_values(by=["include_in_universe", "ticker"], ascending=[False, True])