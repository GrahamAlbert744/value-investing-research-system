"""
Tests for C6 transparent rule-based stock scoring.

C6 policy:
- Missing metrics receive zero direct score.
- Category scores are reweighted only when category coverage is sufficient.
- Low-coverage categories are not reweighted.
- Score confidence is based on overall data coverage and risk flags.
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
    """Return a small C6-compatible scoring config for tests."""
    return {
        "score_model": {
            "total_points": 100,
            "category_scoring_policy": {
                "min_category_coverage_for_reweight": 0.60,
            },
            "score_confidence_policy": {
                "high_overall_coverage": 0.85,
                "medium_overall_coverage": 0.70,
                "cap_to_medium_if_any_category_below": 0.60,
                "cap_to_low_if_sector_special_handling": True,
                "cap_to_low_if_summary_quality_flags_present": True,
            },
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
                            "target_range": {
                                "min": 0.6,
                                "max": 1.3,
                            },
                            "thresholds": {
                                "poor": 2.5,
                            },
                        }
                    ],
                },
            },
        },
        "missing_value_policy": {
            "missing_metric_score": 0,
            "reweight_observed_metrics_only": True,
            "min_category_coverage_for_reweight": 0.60,
        },
        "sector_special_handling": {
            "financials": {
                "matching_keywords": ["financial", "bank", "insurance"],
                "confidence_cap": "low",
                "reason": "Financial companies need sector-specific scoring.",
            }
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
            "market_capitalization": 3000000000000,
            "pe_ratio": 12,
            "trailing_pe": 13,
            "revenue_growth_yoy": 0.10,
            "latest_net_margin": 0.22,
            "beta": 1.0,
            "summary_quality_flags": "",
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


def test_missing_metric_score_returns_zero_under_c6_policy():
    config = minimal_scoring_config()

    assert missing_metric_score(10, "neutral", config) == 0.0
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
    assert score_lower_is_better(80, 10, thresholds) == 0


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
    assert score_higher_is_better(-0.03, 10, thresholds) == 2
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
    assert result["scorable_points"] == 35.0


def test_score_metric_gives_zero_when_metric_missing():
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
    assert result["metric_score"] == 0.0
    assert result["metric_status"] == "missing"
    assert result["metric_note"] == "missing_no_credit"
    assert result["scorable_points"] == 0.0


def test_score_category_returns_c6_category_fields():
    config = minimal_scoring_config()
    row = sample_company_row()
    category_spec = config["score_model"]["categories"]["value"]

    result = score_category(
        row=row,
        category_name="value",
        category_spec=category_spec,
        scoring_config=config,
    )

    assert result["category_name"] == "value"
    assert result["category_weight"] == 35.0
    assert result["category_score"] == 28.0
    assert result["category_raw_score"] == 28.0
    assert result["category_possible_points"] == 35.0
    assert result["category_scorable_points"] == 35.0
    assert result["category_coverage"] == 1.0
    assert result["category_reweighted"] is True
    assert result["category_confidence"] == "high"
    assert result["missing_metrics"] == []
    assert len(result["metric_results"]) == 1


def test_score_category_does_not_reweight_low_coverage_category():
    config = minimal_scoring_config()
    row = pd.Series({"ticker": "AAPL"})
    category_spec = config["score_model"]["categories"]["value"]

    result = score_category(
        row=row,
        category_name="value",
        category_spec=category_spec,
        scoring_config=config,
    )

    assert result["category_name"] == "value"
    assert result["category_score"] == 0.0
    assert result["category_raw_score"] == 0.0
    assert result["category_coverage"] == 0.0
    assert result["category_reweighted"] is False
    assert result["category_confidence"] == "low"
    assert result["missing_metrics"] == ["pe_ratio"]


def test_score_one_company_returns_expected_c6_output_fields():
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
    assert result["final_score"] == 89.0

    assert result["score_data_coverage"] == 1.0
    assert result["score_confidence"] == "high"
    assert result["missing_metric_count"] == 0
    assert result["missing_metrics"] == ""

    assert result["value_coverage"] == 1.0
    assert result["growth_coverage"] == 1.0
    assert result["quality_coverage"] == 1.0
    assert result["stability_coverage"] == 1.0

    assert "_category_results" in result


def test_score_one_company_lowers_confidence_when_metrics_missing():
    config = minimal_scoring_config()
    row = sample_company_row()
    row["pe_ratio"] = None
    row["trailing_pe"] = None
    row["revenue_growth_yoy"] = None

    result = score_one_company(row=row, scoring_config=config)

    assert result["missing_metric_count"] == 2
    assert "value:pe_ratio" in result["missing_metrics"]
    assert "growth:revenue_growth_yoy" in result["missing_metrics"]
    assert result["score_confidence"] in {"low", "medium"}


def test_score_one_company_caps_financial_sector_confidence():
    config = minimal_scoring_config()
    row = sample_company_row()
    row["sector"] = "Financial Services"
    row["industry"] = "Banks"

    result = score_one_company(row=row, scoring_config=config)

    assert result["score_confidence"] == "low"
    assert "sector_special_handling:financials" in result["score_confidence_notes"]


def test_score_one_company_caps_confidence_when_summary_flags_present():
    config = minimal_scoring_config()
    row = sample_company_row()
    row["summary_quality_flags"] = "negative_equity"

    result = score_one_company(row=row, scoring_config=config)

    assert result["score_confidence"] == "low"
    assert "summary_quality_flags_present" in result["score_confidence_notes"]


def test_merge_scoring_inputs_merges_on_source_symbol():
    normalized_metrics = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "ticker": "AAPL",
                "name": "Apple Inc",
                "sector": "Technology",
            }
        ]
    )

    financial_summary = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "latest_revenue": 400.0,
                "latest_net_margin": 0.25,
            }
        ]
    )

    result = merge_scoring_inputs(
        normalized_metrics=normalized_metrics,
        financial_summary=financial_summary,
    )

    assert len(result) == 1
    assert result.loc[0, "source_symbol"] == "AAPL.US"
    assert result.loc[0, "latest_revenue"] == 400.0
    assert result.loc[0, "latest_net_margin"] == 0.25


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

    assert result.equals(normalized_metrics)


def test_merge_scoring_inputs_raises_error_for_empty_normalized_metrics():
    with pytest.raises(ValueError):
        merge_scoring_inputs(
            normalized_metrics=pd.DataFrame(),
            financial_summary=pd.DataFrame(),
        )


def test_score_companies_scores_and_sorts_rows():
    config = minimal_scoring_config()

    scoring_input = pd.DataFrame(
        [
            sample_company_row().to_dict(),
            {
                **sample_company_row().to_dict(),
                "source_symbol": "WEAK.US",
                "ticker": "WEAK",
                "pe_ratio": 80,
                "revenue_growth_yoy": -0.20,
                "latest_net_margin": -0.05,
                "beta": 3.0,
            },
        ]
    )

    result = score_companies(
        scoring_input=scoring_input,
        scoring_config=config,
    )

    assert len(result) == 2
    assert result.loc[0, "source_symbol"] == "AAPL.US"
    assert result.loc[0, "final_score"] > result.loc[1, "final_score"]


def test_score_companies_handles_empty_input():
    config = minimal_scoring_config()

    result = score_companies(
        scoring_input=pd.DataFrame(),
        scoring_config=config,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty