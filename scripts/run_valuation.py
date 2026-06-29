"""
Run conservative valuation.

Inputs:
- config/valuation_config.yml
- outputs/normalized_metrics.csv
- outputs/financial_statement_summary.csv
- outputs/all_scored_stocks.csv

Output:
- outputs/valuation_outputs.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.valuation import (
    build_valuation_outputs,
    load_valuation_config,
    merge_valuation_inputs,
)


def main() -> None:
    valuation_config_path = PROJECT_ROOT / "config" / "valuation_config.yml"
    normalized_metrics_path = PROJECT_ROOT / "outputs" / "normalized_metrics.csv"
    financial_summary_path = PROJECT_ROOT / "outputs" / "financial_statement_summary.csv"
    scored_stocks_path = PROJECT_ROOT / "outputs" / "all_scored_stocks.csv"
    output_path = PROJECT_ROOT / "outputs" / "valuation_outputs.csv"

    if not valuation_config_path.exists():
        raise FileNotFoundError(
            f"Missing valuation config: {valuation_config_path}"
        )

    if not normalized_metrics_path.exists():
        raise FileNotFoundError(
            f"Missing normalized metrics: {normalized_metrics_path}"
        )

    if not financial_summary_path.exists():
        raise FileNotFoundError(
            f"Missing financial statement summary: {financial_summary_path}"
        )

    if not scored_stocks_path.exists():
        raise FileNotFoundError(
            f"Missing scored stocks output: {scored_stocks_path}"
        )

    print(f"Loading valuation config: {valuation_config_path}")
    print(f"Loading normalized metrics: {normalized_metrics_path}")
    print(f"Loading financial summary: {financial_summary_path}")
    print(f"Loading scored stocks: {scored_stocks_path}")

    valuation_config = load_valuation_config(valuation_config_path)
    normalized_metrics = pd.read_csv(normalized_metrics_path)
    financial_summary = pd.read_csv(financial_summary_path)
    scored_stocks = pd.read_csv(scored_stocks_path)

    valuation_input = merge_valuation_inputs(
        normalized_metrics=normalized_metrics,
        financial_summary=financial_summary,
        scored_stocks=scored_stocks,
    )

    valuation_outputs = build_valuation_outputs(
        valuation_input=valuation_input,
        valuation_config=valuation_config,
    )

    valuation_outputs.to_csv(output_path, index=False)

    print(f"\nValuation outputs saved to: {output_path}")
    print(f"Rows valued: {len(valuation_outputs)}")

    if valuation_outputs.empty:
        print("\nNo valuation rows created.")
    else:
        preview_columns = [
            "source_symbol",
            "name",
            "market_capitalization",
            "final_score",
            "valuation_confidence",
            "conservative_value_low",
            "conservative_value_base",
            "conservative_value_high",
            "margin_of_safety_base",
            "margin_of_safety_label",
            "methods_available",
            "methods_missing",
            "valuation_flags",
        ]

        available_columns = [
            column
            for column in preview_columns
            if column in valuation_outputs.columns
        ]

        print("\nValuation preview:")
        print(valuation_outputs[available_columns].to_string(index=False))


if __name__ == "__main__":
    main()