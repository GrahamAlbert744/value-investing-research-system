"""
Transparent rule-based scoring functions.

C6 scoring policy:
- Missing metrics receive no score.
- Category scores are reweighted only when category coverage >= configured threshold.
- Low-coverage categories are not reweighted.
- Score confidence is based on overall coverage, category coverage, summary flags, and sector caveats.
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
    """Convert value to float when possible."""
    if is_missing(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_metric_value(
    row: pd.Series,
    metric_spec: dict[str, Any],
) -> tuple[float | None, str | None]:
    """Get metric value from primary field or fallback fields."""
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
    """
    Backward-compatible helper.

    C6 policy: missing metrics receive zero direct score.
    """
    return 0.0


def score_lower_is_better(
    value: float,
    points: float,
    thresholds: dict[str, Any],
) -> float:
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


def score_higher_is_better(
    value: float,
    points: float,
    thresholds: dict[str, Any],
) -> float:
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


def score_target_range(
    value: float,
    points: float,
    metric_spec: dict[str, Any],
) -> float:
    """Score a metric where a middle range is preferred."""
    target_range = metric_spec.get("target_range", {})
    min_value = float(target_range["min"])
    max_value = float(target_range["max"])

    if min_value <= value <= max_value:
        return points

    thresholds = metric_spec.get("thresholds", {})
    poor = float(thresholds.get("poor", max_value * 2))

    if value < min_value:
        distance = min_value - value
        denominator = max(min_value, 1.0)
    else:
        distance = value - max_value
        denominator = max(poor - max_value, 1.0)

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

    value, field_used = get_metric_value(row=row, metric_spec=metric_spec)

    if value is None:
        return {
            "metric_name": metric_name,
            "field_used": None,
            "metric_value": None,
            "metric_points": points,
            "metric_score": 0.0,
            "metric_status": "missing",
            "metric_note": "missing_no_credit",
            "scorable_points": 0.0,
        }

    if direction == "lower_is_better":
        metric_score = score_lower_is_better(
            value=value,
            points=points,
            thresholds=metric_spec["thresholds"],
        )
    elif direction == "higher_is_better":
        metric_score = score_higher_is_better(
            value=value,
            points=points,
            thresholds=metric_spec["thresholds"],
        )
    elif direction == "target_range":
        metric_score = score_target_range(
            value=value,
            points=points,
            metric_spec=metric_spec,
        )
    else:
        raise ValueError(f"Unsupported metric direction: {direction}")

    return {
        "metric_name": metric_name,
        "field_used": field_used,
        "metric_value": value,
        "metric_points": points,
        "metric_score": round(metric_score, 4),
        "metric_status": "scored",
        "metric_note": "",
        "scorable_points": points,
    }


def get_category_reweight_threshold(scoring_config: dict[str, Any]) -> float:
    """Return minimum coverage required before category reweighting."""
    policy = scoring_config.get("score_model", {}).get(
        "category_scoring_policy",
        {},
    )

    return float(
        policy.get(
            "min_category_coverage_for_reweight",
            scoring_config.get("missing_value_policy", {}).get(
                "min_category_coverage_for_reweight",
                0.60,
            ),
        )
    )


def score_category(
    row: pd.Series,
    category_name: str,
    category_spec: dict[str, Any],
    scoring_config: dict[str, Any],
) -> dict[str, Any]:
    """Score one category using C6 coverage-based reweighting."""
    category_weight = float(category_spec["weight"])
    metrics = category_spec.get("metrics", [])

    metric_results = [
        score_metric(
            row=row,
            metric_spec=metric_spec,
            scoring_config=scoring_config,
        )
        for metric_spec in metrics
    ]

    raw_score = sum(float(result["metric_score"]) for result in metric_results)
    scorable_points = sum(float(result["scorable_points"]) for result in metric_results)
    possible_points = sum(float(result["metric_points"]) for result in metric_results)

    if possible_points <= 0:
        coverage = 0.0
    else:
        coverage = scorable_points / possible_points

    reweight_threshold = get_category_reweight_threshold(scoring_config)

    if coverage >= reweight_threshold and scorable_points > 0:
        category_score = (raw_score / scorable_points) * category_weight
        category_reweighted = True
        category_note = "reweighted_observed_metrics"
    else:
        category_score = raw_score
        category_reweighted = False
        category_note = "not_reweighted_low_coverage"

    if coverage >= 0.85:
        category_confidence = "high"
    elif coverage >= reweight_threshold:
        category_confidence = "medium"
    else:
        category_confidence = "low"

    missing_metrics = [
        result["metric_name"]
        for result in metric_results
        if result["metric_status"] == "missing"
    ]

    return {
        "category_name": category_name,
        "category_weight": category_weight,
        "category_score": round(category_score, 4),
        "category_raw_score": round(raw_score, 4),
        "category_possible_points": round(possible_points, 4),
        "category_scorable_points": round(scorable_points, 4),
        "category_coverage": round(coverage, 4),
        "category_reweighted": category_reweighted,
        "category_confidence": category_confidence,
        "category_note": category_note,
        "missing_metrics": missing_metrics,
        "metric_results": metric_results,
    }


def get_sector_special_handling(
    row: pd.Series,
    scoring_config: dict[str, Any],
) -> tuple[str, str, str]:
    """Return sector confidence cap, rule name, and reason."""
    sector_text = " ".join(
        str(row.get(column, ""))
        for column in ["sector", "industry"]
    ).lower()

    rules = scoring_config.get("sector_special_handling", {})

    for rule_name, rule in rules.items():
        for keyword in rule.get("matching_keywords", []):
            if str(keyword).lower() in sector_text:
                return (
                    str(rule.get("confidence_cap", "")),
                    rule_name,
                    str(rule.get("reason", "")),
                )

    return "", "", ""


def apply_confidence_cap(confidence: str, cap: str) -> str:
    """Cap confidence at medium or low."""
    confidence_order = {
        "low": 0,
        "medium": 1,
        "high": 2,
    }

    if not cap:
        return confidence

    if cap not in confidence_order or confidence not in confidence_order:
        return confidence

    if confidence_order[confidence] > confidence_order[cap]:
        return cap

    return confidence


def determine_score_confidence(
    category_results: list[dict[str, Any]],
    score_data_coverage: float,
    row: pd.Series,
    scoring_config: dict[str, Any],
) -> tuple[str, list[str]]:
    """Determine score confidence and confidence notes."""
    policy = scoring_config.get("score_model", {}).get("score_confidence_policy", {})

    high_threshold = float(policy.get("high_overall_coverage", 0.85))
    medium_threshold = float(policy.get("medium_overall_coverage", 0.70))
    category_cap_threshold = float(policy.get("cap_to_medium_if_any_category_below", 0.60))

    notes: list[str] = []

    if score_data_coverage >= high_threshold:
        confidence = "high"
    elif score_data_coverage >= medium_threshold:
        confidence = "medium"
    else:
        confidence = "low"

    low_categories = [
        result["category_name"]
        for result in category_results
        if float(result["category_coverage"]) < category_cap_threshold
    ]

    if low_categories:
        confidence = apply_confidence_cap(confidence, "medium")
        notes.append("category_coverage_below_threshold:" + ",".join(low_categories))

    sector_cap, sector_rule, sector_reason = get_sector_special_handling(
        row=row,
        scoring_config=scoring_config,
    )

    if sector_cap and policy.get("cap_to_low_if_sector_special_handling", True):
        confidence = apply_confidence_cap(confidence, sector_cap)
        notes.append(f"sector_special_handling:{sector_rule}")
        if sector_reason:
            notes.append(sector_reason)

    summary_quality_flags = row.get("summary_quality_flags")
    if (
        policy.get("cap_to_low_if_summary_quality_flags_present", True)
        and not is_missing(summary_quality_flags)
        and str(summary_quality_flags).strip() != ""
    ):
        confidence = apply_confidence_cap(confidence, "low")
        notes.append("summary_quality_flags_present")

    return confidence, notes


def score_one_company(
    row: pd.Series,
    scoring_config: dict[str, Any],
) -> dict[str, Any]:
    """Score one company row."""
    categories = scoring_config["score_model"]["categories"]

    category_results = [
        score_category(
            row=row,
            category_name=category_name,
            category_spec=category_spec,
            scoring_config=scoring_config,
        )
        for category_name, category_spec in categories.items()
    ]

    final_score = sum(float(result["category_score"]) for result in category_results)

    total_possible_points = sum(
        float(result["category_possible_points"]) for result in category_results
    )
    total_scorable_points = sum(
        float(result["category_scorable_points"]) for result in category_results
    )

    score_data_coverage = (
        total_scorable_points / total_possible_points
        if total_possible_points > 0
        else 0.0
    )

    missing_metrics = []
    for category_result in category_results:
        for metric_name in category_result["missing_metrics"]:
            missing_metrics.append(f"{category_result['category_name']}:{metric_name}")

    score_confidence, confidence_notes = determine_score_confidence(
        category_results=category_results,
        score_data_coverage=score_data_coverage,
        row=row,
        scoring_config=scoring_config,
    )

    result: dict[str, Any] = {
        "source_symbol": row.get("source_symbol"),
        "ticker": row.get("ticker"),
        "name": row.get("name"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "market_capitalization": row.get("market_capitalization"),
        "final_score": round(final_score, 2),
        "score_data_coverage": round(score_data_coverage, 4),
        "score_confidence": score_confidence,
        "score_confidence_notes": ";".join(confidence_notes),
        "missing_metric_count": len(missing_metrics),
        "missing_metrics": ";".join(missing_metrics),
    }

    for category_result in category_results:
        category_name = category_result["category_name"]

        result[f"{category_name}_score"] = round(
            float(category_result["category_score"]),
            2,
        )
        result[f"{category_name}_coverage"] = category_result["category_coverage"]
        result[f"{category_name}_confidence"] = category_result["category_confidence"]
        result[f"{category_name}_reweighted"] = category_result["category_reweighted"]

    result["_category_results"] = category_results

    return result


def merge_scoring_inputs(
    normalized_metrics: pd.DataFrame,
    financial_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Merge normalized company metrics and financial statement summary."""
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


def score_companies(
    scoring_input: pd.DataFrame,
    scoring_config: dict[str, Any],
) -> pd.DataFrame:
    """Score all companies in a merged scoring input table."""
    rows = []

    for _, row in scoring_input.iterrows():
        result = score_one_company(
            row=row,
            scoring_config=scoring_config,
        )
        result.pop("_category_results", None)
        rows.append(result)

    scored = pd.DataFrame(rows)

    if scored.empty:
        return scored

    return scored.sort_values(
        by=["final_score", "score_data_coverage"],
        ascending=[False, False],
    ).reset_index(drop=True)