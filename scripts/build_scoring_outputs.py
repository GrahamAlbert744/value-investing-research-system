"""
Build enhanced scoring outputs.

Inputs:
- config/scoring_config.yml
- outputs/normalized_metrics.csv
- outputs/financial_statement_summary.csv

Outputs:
- outputs/all_scored_stocks.csv
- outputs/scoring_metric_details.csv
- outputs/rejected_stocks.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.scoring import load_scoring_config
from src.scoring_outputs import build_scoring_outputs


def main() -> None:
    scoring_config_path = PROJECT_ROOT / "config" / "scoring_config.yml"
    normalized_metrics_path = PROJECT_ROOT / "outputs" / "normalized_metrics.csv"
    financial_summary_path = PROJECT_ROOT / "outputs" / "financial_statement_summary.csv"

    all_scored_output_path = PROJECT_ROOT / "outputs" / "all_scored_stocks.csv"
    metric_details_output_path = PROJECT_ROOT / "outputs" / "scoring_metric_details.csv"
    rejected_output_path = PROJECT_ROOT / "outputs" / "rejected_stocks.csv"

    if not scoring_config_path.exists():
        raise FileNotFoundError(
            f"Missing scoring config: {scoring_config_path}"
        )

    if not normalized_metrics_path.exists():
        raise FileNotFoundError(
            f"Missing normalized metrics file: {normalized_metrics_path}\n"
            "Run scripts\\normalize_latest_fundamentals.py first."
        )

    if not financial_summary_path.exists():
        raise FileNotFoundError(
            f"Missing financial statement summary file: {financial_summary_path}\n"
            "Run scripts\\build_financial_statement_summary.py first."
        )

    print(f"Loading scoring config: {scoring_config_path}")
    print(f"Loading normalized metrics: {normalized_metrics_path}")
    print(f"Loading financial statement summary: {financial_summary_path}")

    scoring_config = load_scoring_config(scoring_config_path)
    normalized_metrics = pd.read_csv(normalized_metrics_path)
    financial_summary = pd.read_csv(financial_summary_path)

    outputs = build_scoring_outputs(
        normalized_metrics=normalized_metrics,
        financial_summary=financial_summary,
        scoring_config=scoring_config,
    )

    outputs["all_scored_stocks"].to_csv(all_scored_output_path, index=False)
    outputs["scoring_metric_details"].to_csv(metric_details_output_path, index=False)
    outputs["rejected_stocks"].to_csv(rejected_output_path, index=False)

    print(f"\nEnhanced scored stocks saved to: {all_scored_output_path}")
    print(f"Metric-level details saved to: {metric_details_output_path}")
    print(f"Rejected stocks saved to: {rejected_output_path}")

    all_scored = outputs["all_scored_stocks"]
    metric_details = outputs["scoring_metric_details"]
    rejected = outputs["rejected_stocks"]

    print(f"\nRows scored: {len(all_scored)}")
    print(f"Metric detail rows: {len(metric_details)}")
    print(f"Rejected rows: {len(rejected)}")

    if not all_scored.empty:
        print("\nRanking status counts:")
        print(all_scored["ranking_status"].value_counts().to_string())

        print("\nScored preview:")
        preview_columns = [
            "source_symbol",
            "name",
            "final_score",
            "value_score",
            "growth_score",
            "quality_score",
            "stability_score",
            "score_confidence",
            "ranking_status",
            "rejection_reasons",
            "watchlist_reasons",
        ]

        available_preview_columns = [
            column for column in preview_columns if column in all_scored.columns
        ]

        print(all_scored[available_preview_columns].to_string(index=False))


if __name__ == "__main__":
    main()