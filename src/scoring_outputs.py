"""
Enhanced scoring outputs.

This module builds:
- metric-level scoring detail
- enhanced all_scored_stocks output
- rejected_stocks output

It uses the transparent scoring functions from src/scoring.py.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.scoring import (
    is_missing,
    merge_scoring_inputs,
    safe_float,
    score_category,
    score_companies,
)


def build_metric_level_details(
    scoring_input: pd.DataFrame,
    scoring_config: dict[str, Any],
) -> pd.DataFrame:
    """Build one row per company/category/metric scored."""
    if scoring_input.empty:
        return pd.DataFrame(
            columns=[
                "source_symbol",
                "ticker",
                "name",
                "sector",
                "industry",
                "category",
                "metric_name",
                "field_used",
                "metric_value",
                "metric_points",
                "metric_score",
                "metric_status",
                "metric_note",
            ]
        )

    categories = scoring_config["score_model"]["categories"]
    rows: list[dict[str, Any]] = []

    for _, company_row in scoring_input.iterrows():
        for category_name, category_spec in categories.items():
            category_result = score_category(
                row=company_row,
                category_name=category_name,
                category_spec=category_spec,
                scoring_config=scoring_config,
            )

            for metric_result in category_result["metric_results"]:
                rows.append(
                    {
                        "source_symbol": company_row.get("source_symbol"),
                        "ticker": company_row.get("ticker"),
                        "name": company_row.get("name"),
                        "sector": company_row.get("sector"),
                        "industry": company_row.get("industry"),
                        "category": category_name,
                        "metric_name": metric_result["metric_name"],
                        "field_used": metric_result["field_used"],
                        "metric_value": metric_result["metric_value"],
                        "metric_points": metric_result["metric_points"],
                        "metric_score": round(metric_result["metric_score"], 2),
                        "metric_status": metric_result["metric_status"],
                        "metric_note": metric_result["metric_note"],
                    }
                )

    details = pd.DataFrame(rows)

    return details.sort_values(
        by=["source_symbol", "category", "metric_name"],
        ascending=True,
    )


def get_missing_critical_fields(
    input_row: pd.Series,
    scoring_config: dict[str, Any],
) -> list[str]:
    """Return critical fields that are missing for one stock."""
    policy = scoring_config.get("missing_value_policy", {})
    critical_fields = policy.get("critical_missing_fields", [])

    missing_fields: list[str] = []

    for field in critical_fields:
        if field not in input_row.index or is_missing(input_row.get(field)):
            missing_fields.append(field)

    return missing_fields


def build_ranking_decision(
    scored_row: pd.Series,
    input_row: pd.Series,
    scoring_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Decide whether a stock is rankable, watchlist, or rejected.

    Rejected:
    - missing critical identity / ranking fields

    Watchlist:
    - low score confidence
    - missing metrics
    - very low final score

    Rankable:
    - no rejection reasons and no watchlist reasons
    """
    missing_critical_fields = get_missing_critical_fields(
        input_row=input_row,
        scoring_config=scoring_config,
    )

    rejection_reasons: list[str] = []
    watchlist_reasons: list[str] = []

    if missing_critical_fields:
        rejection_reasons.append(
            "critical_missing_fields:" + ",".join(missing_critical_fields)
        )

    final_score = safe_float(scored_row.get("final_score"))
    missing_metric_count = int(scored_row.get("missing_metric_count", 0))
    score_confidence = str(scored_row.get("score_confidence", "")).lower()

    minimum_rankable_score = float(
        scoring_config.get("ranking_policy", {}).get(
            "minimum_rankable_score",
            50,
        )
    )

    if score_confidence == "low":
        watchlist_reasons.append("low_score_confidence")

    if missing_metric_count > 0:
        watchlist_reasons.append(f"missing_metric_count:{missing_metric_count}")

    if final_score is not None and final_score < minimum_rankable_score:
        watchlist_reasons.append(
            f"final_score_below_{minimum_rankable_score:g}"
        )

    if rejection_reasons:
        ranking_status = "rejected"
        is_rankable = False
    elif watchlist_reasons:
        ranking_status = "watchlist"
        is_rankable = False
    else:
        ranking_status = "rankable"
        is_rankable = True

    return {
        "ranking_status": ranking_status,
        "is_rankable": is_rankable,
        "rejection_reasons": ";".join(rejection_reasons),
        "watchlist_reasons": ";".join(watchlist_reasons),
    }


def enhance_scored_stocks(
    scoring_input: pd.DataFrame,
    scored_stocks: pd.DataFrame,
    scoring_config: dict[str, Any],
) -> pd.DataFrame:
    """Add ranking status and rejection/watchlist reasons to scored stocks."""
    if scored_stocks.empty:
        return scored_stocks.copy()

    if "source_symbol" not in scored_stocks.columns:
        raise ValueError("scored_stocks must include source_symbol.")

    if "source_symbol" not in scoring_input.columns:
        raise ValueError("scoring_input must include source_symbol.")

    input_lookup = (
        scoring_input.drop_duplicates(subset=["source_symbol"])
        .set_index("source_symbol", drop=False)
    )

    enhanced_rows: list[dict[str, Any]] = []

    for _, scored_row in scored_stocks.iterrows():
        source_symbol = scored_row.get("source_symbol")

        if source_symbol in input_lookup.index:
            input_row = input_lookup.loc[source_symbol]
        else:
            input_row = pd.Series(dtype=object)

        decision = build_ranking_decision(
            scored_row=scored_row,
            input_row=input_row,
            scoring_config=scoring_config,
        )

        row = scored_row.to_dict()
        row.update(decision)

        final_score = row.get("final_score")
        score_confidence = row.get("score_confidence")
        row["score_summary"] = f"{final_score}/100 ({score_confidence} confidence)"

        enhanced_rows.append(row)

    enhanced = pd.DataFrame(enhanced_rows)

    return enhanced.sort_values(
        by=["is_rankable", "final_score", "source_symbol"],
        ascending=[False, False, True],
    )


def build_rejected_stocks(enhanced_scored_stocks: pd.DataFrame) -> pd.DataFrame:
    """Create rejected_stocks output from enhanced scored stocks."""
    if enhanced_scored_stocks.empty:
        return pd.DataFrame()

    rejected = enhanced_scored_stocks[
        enhanced_scored_stocks["ranking_status"] == "rejected"
    ].copy()

    output_columns = [
        "source_symbol",
        "ticker",
        "name",
        "sector",
        "industry",
        "final_score",
        "score_confidence",
        "missing_metric_count",
        "ranking_status",
        "rejection_reasons",
        "watchlist_reasons",
        "scoring_notes",
    ]

    available_columns = [
        column for column in output_columns if column in rejected.columns
    ]

    return rejected[available_columns]


def build_scoring_outputs(
    normalized_metrics: pd.DataFrame,
    financial_summary: pd.DataFrame,
    scoring_config: dict[str, Any],
) -> dict[str, pd.DataFrame]:
    """Build all scoring outputs from normalized and financial summary inputs."""
    scoring_input = merge_scoring_inputs(
        normalized_metrics=normalized_metrics,
        financial_summary=financial_summary,
    )

    scored_stocks = score_companies(
        scoring_input=scoring_input,
        scoring_config=scoring_config,
    )

    metric_details = build_metric_level_details(
        scoring_input=scoring_input,
        scoring_config=scoring_config,
    )

    enhanced_scored_stocks = enhance_scored_stocks(
        scoring_input=scoring_input,
        scored_stocks=scored_stocks,
        scoring_config=scoring_config,
    )

    rejected_stocks = build_rejected_stocks(enhanced_scored_stocks)

    return {
        "all_scored_stocks": enhanced_scored_stocks,
        "scoring_metric_details": metric_details,
        "rejected_stocks": rejected_stocks,
    }