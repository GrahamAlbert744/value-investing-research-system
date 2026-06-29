"""
Tests for transparent rule-based stock scoring.

These tests use small fake DataFrames and dictionaries, so they do not require:
- API access
- .env
- raw EODHD JSON files
"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.scoring import (
    get_metric_value,
    is_missing,
    load_scoring_config,
    merge_scoring_inputs,
    missing_metric_score,
    safe_float,
    score_category,
    score_companies,
    score_higher_is_better,
    score_lower_is_better,
    score_metric,
    score_one_company,
    score_target_range,
)


def minimal_scoring_config() -> dict:
    """Return a small scoring config for tests."""
    return {
        "score_model": {
            "total_points": 100,
            "categories": {
                "value": {
                    "weight": 35,
                    "metrics": [
                        {
                            "name": "pe_ratio",
                            "field": "pe_ratio",
                            "fallback_fields": ["trailing_pe"],
                            "points": 35,
                            "direction": "lower_is_better",
                            "missing_action": "neutral",
                            "thresholds": {
                                "excellent": 10,
                                "good": 15,
                                "fair": 25,
                                "weak": 40,
                                "poor": 60,
                            },
                        }
                    ],
                },
                "growth": {
                    "weight": 20,
                    "metrics": [
                        {
                            "name": "revenue_growth_yoy",
                            "field": "revenue_growth_yoy",
                            "points": 20,
                            "direction": "higher_is_better",
                            "missing_action": "neutral",
                            "thresholds": {
                                "excellent": 0.15,
                                "good": 0.08,
                                "fair": 0.03,
                                "weak": 0,
                                "poor": -0.05,
                            },
                        }
                    ],
                },
                "quality": {
                    "weight": 35,
                    "metrics": [
                        {
                            "name": "latest_net_margin",
                            "field": "latest_net_margin",
                            "points": 35,
                            "direction": "higher_is_better",
                            "missing_action": "neutral",
                            "thresholds": {
                                "excellent": 0.20,
                                "good": 0.12,
                                "fair": 0.07,
                                "weak": 0.03,
                                "poor": 0,
                            },
                        }
                    ],
                },
                "stability": {
                    "weight": 10,
                    "metrics": [
                        {
                            "name": "beta",
                            "field": "beta",
                            "points": 10,
                            "direction": "target_range",
                            "missing_action": "neutral",
                            "target_range": {
                                "min": 0.6,
                                "max": 1.3,
                            },
                            "thresholds": {
                                "excellent": 1.0,
                                "good": 1.3,
                                "fair": 1.6,
                                "weak": 2.0,
                                "poor": 2.5,
                            },
                        }
                    ],
                },
            },
        },
        "missing_value_policy": {
            "neutral_score_fraction": 0.50,
            "zero_score_fraction": 0.00,
        },
    }


def sample_company_row() -> pd.Series:
    """Return one fake scoring input row."""
    return pd.Series(
        {
            "source_symbol": "AAPL.US",
            "ticker": "AAPL",
            "name": "Apple Inc",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "pe_ratio": 12,
            "trailing_pe": 13,
            "revenue_growth_yoy": 0.10,
            "latest_net_margin": 0.22,
            "beta": 1.0,
        }
    )


def test_load_scoring_config_reads_yaml(tmp_path: Path):
    config_path = tmp_path / "scoring_config.yml"
    config = minimal_scoring_config()

    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(config, file)

    loaded = load_scoring_config(config_path)

    assert loaded["score_model"]["total_points"] == 100
    assert set(loaded["score_model"]["categories"].keys()) == {
        "value",
        "growth",
        "quality",
        "stability",
    }


def test_load_scoring_config_missing_file_raises_error(tmp_path: Path):
    missing_path = tmp_path / "missing_scoring_config.yml"

    with pytest.raises(FileNotFoundError):
        load_scoring_config(missing_path)


def test_is_missing_detects_none_blank_and_nan():
    assert is_missing(None)
    assert is_missing("")
    assert is_missing("   ")
    assert is_missing(float("nan"))
    assert not is_missing("AAPL")
    assert not is_missing(0)


def test_safe_float_converts_valid_values():
    assert safe_float("10.5") == 10.5
    assert safe_float(42) == 42.0
    assert safe_float(-1) == -1.0


def test_safe_float_returns_none_for_invalid_values():
    assert safe_float(None) is None
    assert safe_float("") is None
    assert safe_float("not_a_number") is None


def test_get_metric_value_uses_primary_field_first():
    row = pd.Series(
        {
            "pe_ratio": 12,
            "trailing_pe": 15,
        }
    )

    metric_spec = {
        "field": "pe_ratio",
        "fallback_fields": ["trailing_pe"],
    }

    value, field_used = get_metric_value(row, metric_spec)

    assert value == 12.0
    assert field_used == "pe_ratio"


def test_get_metric_value_uses_fallback_when_primary_missing():
    row = pd.Series(
        {
            "pe_ratio": None,
            "trailing_pe": 15,
        }
    )

    metric_spec = {
        "field": "pe_ratio",
        "fallback_fields": ["trailing_pe"],
    }

    value, field_used = get_metric_value(row, metric_spec)

    assert value == 15.0
    assert field_used == "trailing_pe"


def test_missing_metric_score_uses_neutral_and_zero_policy():
    config = minimal_scoring_config()

    assert missing_metric_score(10, "neutral", config) == 5.0
    assert missing_metric_score(10, "zero", config) == 0.0


def test_score_lower_is_better_awards_expected_points():
    thresholds = {
        "excellent": 10,
        "good": 15,
        "fair": 25,
        "weak": 40,
        "poor": 60,
    }

    assert score_lower_is_better(8, 10, thresholds) == 10
    assert score_lower_is_better(12, 10, thresholds) == 8
    assert score_lower_is_better(20, 10, thresholds) == 6
    assert score_lower_is_better(35, 10, thresholds) == 4
    assert score_lower_is_better(50, 10, thresholds) == 2
    assert score_lower_is_better(100, 10, thresholds) == 0


def test_score_higher_is_better_awards_expected_points():
    thresholds = {
        "excellent": 0.15,
        "good": 0.08,
        "fair": 0.03,
        "weak": 0,
        "poor": -0.05,
    }

    assert score_higher_is_better(0.20, 10, thresholds) == 10
    assert score_higher_is_better(0.10, 10, thresholds) == 8
    assert score_higher_is_better(0.05, 10, thresholds) == 6
    assert score_higher_is_better(0.01, 10, thresholds) == 4
    assert score_higher_is_better(-0.02, 10, thresholds) == 2
    assert score_higher_is_better(-0.20, 10, thresholds) == 0


def test_score_target_range_awards_full_points_inside_range():
    metric_spec = {
        "target_range": {
            "min": 0.6,
            "max": 1.3,
        },
        "thresholds": {
            "poor": 2.5,
        },
    }

    assert score_target_range(1.0, 10, metric_spec) == 10


def test_score_metric_scores_present_metric():
    config = minimal_scoring_config()
    row = sample_company_row()

    metric_spec = config["score_model"]["categories"]["value"]["metrics"][0]

    result = score_metric(
        row=row,
        metric_spec=metric_spec,
        scoring_config=config,
    )

    assert result["metric_name"] == "pe_ratio"
    assert result["field_used"] == "pe_ratio"
    assert result["metric_value"] == 12.0
    assert result["metric_score"] == 28.0
    assert result["metric_status"] == "scored"


def test_score_metric_uses_missing_policy_when_metric_missing():
    config = minimal_scoring_config()
    row = pd.Series({"ticker": "AAPL"})

    metric_spec = config["score_model"]["categories"]["value"]["metrics"][0]

    result = score_metric(
        row=row,
        metric_spec=metric_spec,
        scoring_config=config,
    )

    assert result["metric_name"] == "pe_ratio"
    assert result["metric_value"] is None
    assert result["metric_score"] == 17.5
    assert result["metric_status"] == "missing"


def test_score_category_returns_category_score_and_missing_count():
    config = minimal_scoring_config()
    row = sample_company_row()
    category_spec = config["score_model"]["categories"]["value"]

    result = score_category(
        row=row,
        category_name="value",
        category_spec=category_spec,
        scoring_config=config,
    )

    assert result["category"] == "value"
    assert result["category_points"] == 35
    assert result["category_score"] == 28.0
    assert result["missing_metric_count"] == 0
    assert len(result["metric_results"]) == 1


def test_score_one_company_returns_expected_output_fields():
    config = minimal_scoring_config()
    row = sample_company_row()

    result = score_one_company(row=row, scoring_config=config)

    assert result["source_symbol"] == "AAPL.US"
    assert result["ticker"] == "AAPL"
    assert result["name"] == "Apple Inc"
    assert result["value_score"] == 28.0
    assert result["growth_score"] == 16.0
    assert result["quality_score"] == 35.0
    assert result["stability_score"] == 10.0
    assert result["total_score"] == 89.0
    assert result["final_score"] == 89.0
    assert result["score_confidence"] == "high"
    assert result["missing_metric_count"] == 0


def test_score_one_company_lowers_confidence_when_metrics_missing():
    config = minimal_scoring_config()
    row = pd.Series(
        {
            "source_symbol": "AAPL.US",
            "ticker": "AAPL",
            "name": "Apple Inc",
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }
    )

    result = score_one_company(row=row, scoring_config=config)

    assert result["missing_metric_count"] == 4
    assert result["score_confidence"] == "low"


def test_merge_scoring_inputs_merges_on_source_symbol():
    normalized_metrics = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "ticker": "AAPL",
                "name": "Apple Inc",
                "pe_ratio": 12,
            }
        ]
    )

    financial_summary = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "revenue_growth_yoy": 0.10,
                "latest_net_margin": 0.22,
            }
        ]
    )

    result = merge_scoring_inputs(
        normalized_metrics=normalized_metrics,
        financial_summary=financial_summary,
    )

    assert len(result) == 1
    assert result.loc[0, "source_symbol"] == "AAPL.US"
    assert result.loc[0, "revenue_growth_yoy"] == 0.10
    assert result.loc[0, "latest_net_margin"] == 0.22


def test_merge_scoring_inputs_returns_normalized_metrics_when_summary_empty():
    normalized_metrics = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "ticker": "AAPL",
            }
        ]
    )

    financial_summary = pd.DataFrame()

    result = merge_scoring_inputs(
        normalized_metrics=normalized_metrics,
        financial_summary=financial_summary,
    )

    assert len(result) == 1
    assert result.loc[0, "source_symbol"] == "AAPL.US"
    assert result.loc[0, "ticker"] == "AAPL"


def test_score_companies_scores_and_sorts_rows():
    config = minimal_scoring_config()

    high_score_row = sample_company_row()

    low_score_row = sample_company_row().copy()
    low_score_row["source_symbol"] = "WEAK.US"
    low_score_row["ticker"] = "WEAK"
    low_score_row["name"] = "Weak Company"
    low_score_row["pe_ratio"] = 100
    low_score_row["revenue_growth_yoy"] = -0.20
    low_score_row["latest_net_margin"] = -0.10
    low_score_row["beta"] = 3.0

    scoring_input = pd.DataFrame([high_score_row, low_score_row])

    result = score_companies(
        scoring_input=scoring_input,
        scoring_config=config,
    )

    assert len(result) == 2
    assert result.iloc[0]["source_symbol"] == "AAPL.US"
    assert result.iloc[0]["final_score"] > result.iloc[1]["final_score"]


def test_score_companies_handles_empty_input():
    config = minimal_scoring_config()

    result = score_companies(
        scoring_input=pd.DataFrame(),
        scoring_config=config,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty