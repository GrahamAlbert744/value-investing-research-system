"""
Transparent rule-based scoring functions for the value-investing project.

This module converts normalized company metrics and financial-statement summaries
into a 100-point score based on config/scoring_config.yml.

The model is intentionally:
- transparent
- configurable
- rule-based
- conservative with missing values
- not machine learning
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_scoring_config(config_path: Path) -> dict[str, Any]:
    """Load scoring configuration from YAML."""
    if not config_path.exists():
        raise FileNotFoundError(f"Scoring config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise TypeError("Scoring config must load as a dictionary.")

    return config


def is_missing(value: Any) -> bool:
    """Return True if a value should be treated as missing."""
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
    """Convert a value to float when possible."""
    if is_missing(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_metric_value(row: pd.Series, metric_spec: dict[str, Any]) -> tuple[float | None, str | None]:
    """
    Get metric value from the primary field or fallback fields.

    Returns:
    - numeric value or None
    - field actually used or None
    """
    candidate_fields = [metric_spec["field"]] + metric_spec.get("fallback_fields", [])

    for field in candidate_fields:
        if field in row.index:
            value = safe_float(row.get(field))
            if value is not None:
                return value, field

    return None, None


def missing_metric_score(
    metric_points: float,
    missing_action: str,
    scoring_config: dict[str, Any],
) -> float:
    """Return score for missing metric based on configured policy."""
    policy = scoring_config.get("missing_value_policy", {})
    neutral_fraction = float(policy.get("neutral_score_fraction", 0.5))
    zero_fraction = float(policy.get("zero_score_fraction", 0.0))

    if missing_action == "zero":
        return metric_points * zero_fraction

    if missing_action == "neutral":
        return metric_points * neutral_fraction

    return metric_points * neutral_fraction


def score_lower_is_better(value: float, points: float, thresholds: dict[str, Any]) -> float:
    """Score a metric where lower values are better."""
    if value <= float(thresholds["excellent"]):
        return points
    if value <= float(thresholds["good"]):
        return points * 0.8
    if value <= float(thresholds["fair"]):
        return points * 0.6
    if value <= float(thresholds["weak"]):
        return points * 0.4
    if value <= float(thresholds["poor"]):
        return points * 0.2
    return 0.0


def score_higher_is_better(value: float, points: float, thresholds: dict[str, Any]) -> float:
    """Score a metric where higher values are better."""
    if value >= float(thresholds["excellent"]):
        return points
    if value >= float(thresholds["good"]):
        return points * 0.8
    if value >= float(thresholds["fair"]):
        return points * 0.6
    if value >= float(thresholds["weak"]):
        return points * 0.4
    if value >= float(thresholds["poor"]):
        return points * 0.2
    return 0.0


def score_target_range(value: float, points: float, metric_spec: dict[str, Any]) -> float:
    """
    Score a metric where a middle range is preferred.

    Used first for beta:
    - full points inside target range
    - partial points as value moves outside the range
    """
    target_range = metric_spec.get("target_range", {})
    min_value = float(target_range.get("min"))
    max_value = float(target_range.get("max"))

    if min_value <= value <= max_value:
        return points

    thresholds = metric_spec.get("thresholds", {})
    poor = float(thresholds.get("poor", max_value * 2))

    if value < min_value:
        distance = min_value - value
        denominator = max(min_value, 1)
    else:
        distance = value - max_value
        denominator = max(poor - max_value, 1)

    penalty_fraction = min(distance / denominator, 1.0)
    return points * (1.0 - penalty_fraction)


def score_metric(
    row: pd.Series,
    metric_spec: dict[str, Any],
    scoring_config: dict[str, Any],
) -> dict[str, Any]:
    """Score one metric for one company row."""
    metric_name = metric_spec["name"]
    points = float(metric_spec["points"])
    direction = metric_spec["direction"]
    missing_action = metric_spec.get("missing_action", "neutral")

    value, field_used = get_metric_value(row=row, metric_spec=metric_spec)

    if value is None:
        score = missing_metric_score(
            metric_points=points,
            missing_action=missing_action,
            scoring_config=scoring_config,
        )

        return {
            "metric_name": metric_name,
            "field_used": field_used,
            "metric_value": None,
            "metric_points": points,
            "metric_score": score,
            "metric_status": "missing",
            "metric_note": f"Missing metric; used {missing_action} policy.",
        }

    if direction == "lower_is_better":
        score = score_lower_is_better(
            value=value,
            points=points,
            thresholds=metric_spec["thresholds"],
        )
    elif direction == "higher_is_better":
        score = score_higher_is_better(
            value=value,
            points=points,
            thresholds=metric_spec["thresholds"],
        )
    elif direction == "target_range":
        score = score_target_range(
            value=value,
            points=points,
            metric_spec=metric_spec,
        )
    else:
        raise ValueError(f"Unsupported scoring direction: {direction}")

    return {
        "metric_name": metric_name,
        "field_used": field_used,
        "metric_value": value,
        "metric_points": points,
        "metric_score": score,
        "metric_status": "scored",
        "metric_note": "",
    }


def score_category(
    row: pd.Series,
    category_name: str,
    category_spec: dict[str, Any],
    scoring_config: dict[str, Any],
) -> dict[str, Any]:
    """Score one category such as value, growth, quality, or stability."""
    metric_results = []

    for metric_spec in category_spec.get("metrics", []):
        result = score_metric(
            row=row,
            metric_spec=metric_spec,
            scoring_config=scoring_config,
        )
        result["category"] = category_name
        metric_results.append(result)

    category_score = sum(result["metric_score"] for result in metric_results)
    category_points = sum(result["metric_points"] for result in metric_results)
    missing_count = sum(result["metric_status"] == "missing" for result in metric_results)

    return {
        "category": category_name,
        "category_score": category_score,
        "category_points": category_points,
        "missing_metric_count": missing_count,
        "metric_results": metric_results,
    }


def score_one_company(row: pd.Series, scoring_config: dict[str, Any]) -> dict[str, Any]:
    """Score one company row."""
    categories = scoring_config["score_model"]["categories"]

    category_results = {}

    for category_name, category_spec in categories.items():
        category_results[category_name] = score_category(
            row=row,
            category_name=category_name,
            category_spec=category_spec,
            scoring_config=scoring_config,
        )

    value_score = category_results["value"]["category_score"]
    growth_score = category_results["growth"]["category_score"]
    quality_score = category_results["quality"]["category_score"]
    stability_score = category_results["stability"]["category_score"]

    total_score = value_score + growth_score + quality_score + stability_score
    quality_penalty = 0.0
    final_score = max(total_score - quality_penalty, 0.0)

    missing_metric_count = sum(
        result["missing_metric_count"] for result in category_results.values()
    )

    total_metrics = sum(
        len(category["metrics"]) for category in categories.values()
    )

    if missing_metric_count == 0:
        score_confidence = "high"
    elif missing_metric_count <= max(2, total_metrics * 0.25):
        score_confidence = "medium"
    else:
        score_confidence = "low"

    scoring_notes = []
    if missing_metric_count:
        scoring_notes.append(f"{missing_metric_count} metrics missing or neutral-scored.")

    return {
        "source_symbol": row.get("source_symbol"),
        "ticker": row.get("ticker"),
        "name": row.get("name"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "total_score": round(total_score, 2),
        "value_score": round(value_score, 2),
        "growth_score": round(growth_score, 2),
        "quality_score": round(quality_score, 2),
        "stability_score": round(stability_score, 2),
        "quality_penalty": round(quality_penalty, 2),
        "final_score": round(final_score, 2),
        "score_confidence": score_confidence,
        "missing_metric_count": int(missing_metric_count),
        "data_quality_flag_count": 0,
        "scoring_notes": " ".join(scoring_notes),
    }


def merge_scoring_inputs(
    normalized_metrics: pd.DataFrame,
    financial_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Merge normalized company metrics with financial statement summary metrics."""
    if normalized_metrics.empty:
        raise ValueError("normalized_metrics is empty.")

    if "source_symbol" not in normalized_metrics.columns:
        raise ValueError("normalized_metrics must include source_symbol.")

    if financial_summary.empty:
        return normalized_metrics.copy()

    if "source_symbol" not in financial_summary.columns:
        raise ValueError("financial_summary must include source_symbol.")

    return normalized_metrics.merge(
        financial_summary,
        on="source_symbol",
        how="left",
        suffixes=("", "_financial_summary"),
    )


def score_companies(scoring_input: pd.DataFrame, scoring_config: dict[str, Any]) -> pd.DataFrame:
    """Score all companies in a scoring input DataFrame."""
    if scoring_input.empty:
        return pd.DataFrame()

    rows = []

    for _, row in scoring_input.iterrows():
        rows.append(score_one_company(row=row, scoring_config=scoring_config))

    scored = pd.DataFrame(rows)

    if scored.empty:
        return scored

    return scored.sort_values(by=["final_score", "source_symbol"], ascending=[False, True])