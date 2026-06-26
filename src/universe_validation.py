"""
Validate universe tickers against EODHD exchange-symbol-list metadata.

This module checks whether seed universe tickers exist in EODHD's exchange
symbol list and preserves useful metadata for later universe expansion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def load_universe_master(path: Path) -> pd.DataFrame:
    """Load universe_master.csv."""
    if not path.exists():
        raise FileNotFoundError(f"Universe master file not found: {path}")

    return pd.read_csv(path)


def exchange_symbols_to_dataframe(symbols: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert EODHD exchange-symbol-list response to a DataFrame."""
    df = pd.DataFrame(symbols)

    if df.empty:
        return df

    # Standardize common EODHD columns while preserving originals.
    rename_map = {
        "Code": "eodhd_code",
        "Name": "eodhd_name",
        "Country": "eodhd_country",
        "Exchange": "eodhd_exchange",
        "Currency": "eodhd_currency",
        "Type": "eodhd_type",
        "Isin": "eodhd_isin",
        "ISIN": "eodhd_isin",
    }

    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    if "eodhd_code" not in df.columns:
        raise ValueError(
            "EODHD exchange symbol response did not include a Code column."
        )

    df["eodhd_code"] = df["eodhd_code"].astype(str).str.strip()
    df["eodhd_code_upper"] = df["eodhd_code"].str.upper()

    return df


def build_eodhd_ticker(code: str, exchange_suffix: str) -> str:
    """Build canonical EODHD ticker from code and exchange suffix."""
    return f"{str(code).strip().upper()}.{str(exchange_suffix).strip().upper()}"


def validate_universe_against_exchange_symbols(
    universe_df: pd.DataFrame,
    exchange_symbols_df: pd.DataFrame,
    exchange_suffix: str = "US",
) -> pd.DataFrame:
    """
    Validate universe tickers against EODHD exchange-symbol-list output.

    Returns one row per universe ticker with match status and EODHD metadata.
    """
    if universe_df.empty:
        raise ValueError("universe_df is empty.")

    if exchange_symbols_df.empty:
        raise ValueError("exchange_symbols_df is empty.")

    required_universe_columns = ["ticker", "code", "currency", "include_in_universe"]
    missing_columns = [
        column for column in required_universe_columns if column not in universe_df.columns
    ]

    if missing_columns:
        raise ValueError(
            "universe_df is missing required columns: "
            + ", ".join(missing_columns)
        )

    if "eodhd_code_upper" not in exchange_symbols_df.columns:
        raise ValueError(
            "exchange_symbols_df must include eodhd_code_upper. "
            "Run exchange_symbols_to_dataframe first."
        )

    eodhd_lookup = exchange_symbols_df.set_index("eodhd_code_upper", drop=False)

    rows: list[dict[str, Any]] = []

    for _, row in universe_df.iterrows():
        code = str(row["code"]).strip().upper()
        ticker = str(row["ticker"]).strip().upper()
        expected_ticker = build_eodhd_ticker(code, exchange_suffix)

        match_found = code in eodhd_lookup.index

        eodhd_match = {}
        if match_found:
            match_row = eodhd_lookup.loc[code]

            # If duplicate codes somehow exist, keep first row.
            if isinstance(match_row, pd.DataFrame):
                match_row = match_row.iloc[0]

            eodhd_match = match_row.to_dict()

        universe_currency = str(row.get("currency", "")).strip().upper()
        eodhd_currency = str(eodhd_match.get("eodhd_currency", "")).strip().upper()

        currency_matches = (
            bool(eodhd_currency)
            and bool(universe_currency)
            and universe_currency == eodhd_currency
        )

        validation_status = "pass" if match_found and currency_matches else "flag"

        issues = []
        if not match_found:
            issues.append("missing_from_eodhd_exchange_symbols")
        if match_found and not currency_matches:
            issues.append("currency_mismatch_or_missing")

        rows.append(
            {
                "ticker": ticker,
                "code": code,
                "expected_eodhd_ticker": expected_ticker,
                "include_in_universe": bool(row["include_in_universe"]),
                "found_in_eodhd_exchange_symbols": match_found,
                "currency_matches": currency_matches,
                "validation_status": validation_status,
                "validation_issues": ";".join(issues),
                "universe_company_name": row.get("company_name", ""),
                "universe_currency": universe_currency,
                "eodhd_name": eodhd_match.get("eodhd_name", ""),
                "eodhd_exchange": eodhd_match.get("eodhd_exchange", ""),
                "eodhd_currency": eodhd_currency,
                "eodhd_type": eodhd_match.get("eodhd_type", ""),
                "eodhd_country": eodhd_match.get("eodhd_country", ""),
                "eodhd_isin": eodhd_match.get("eodhd_isin", ""),
            }
        )

    return pd.DataFrame(rows)