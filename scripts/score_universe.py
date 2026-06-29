"""
Score the current normalized universe using config/scoring_config.yml.

Inputs:
- outputs/normalized_metrics.csv
- outputs/financial_statement_summary.csv
- config/scoring_config.yml

Output:
- outputs/all_scored_stocks.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.scoring import (
    load_scoring_config,
    merge_scoring_inputs,
    score_companies,
)


def main() -> None:
    scoring_config_path = PROJECT_ROOT / "config" / "scoring_config.yml"
    normalized_metrics_path = PROJECT_ROOT / "outputs" / "normalized_metrics.csv"
    financial_summary_path = PROJECT_ROOT / "outputs" / "financial_statement_summary.csv"
    output_path = PROJECT_ROOT / "outputs" / "all_scored_stocks.csv"

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

    scoring_input = merge_scoring_inputs(
        normalized_metrics=normalized_metrics,
        financial_summary=financial_summary,
    )

    scored = score_companies(
        scoring_input=scoring_input,
        scoring_config=scoring_config,
    )

    scored.to_csv(output_path, index=False)

    print(f"\nScored stocks saved to: {output_path}")
    print(f"Rows scored: {len(scored)}")

    if scored.empty:
        print("\nNo scored rows created.")
    else:
        print("\nScored preview:")
        print(
            scored[
                [
                    "source_symbol",
                    "name",
                    "final_score",
                    "value_score",
                    "growth_score",
                    "quality_score",
                    "stability_score",
                    "score_confidence",
                    "missing_metric_count",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()