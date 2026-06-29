"""
Tests for enhanced scoring outputs and rejection logic.

These tests use small fake DataFrames and dictionaries, so they do not require:
- API access
- .env
- raw EODHD JSON files
"""

import pandas as pd

from src.scoring_outputs import (
    build_metric_level_details,
    build_ranking_decision,
    build_rejected_stocks,
    build_scoring_outputs,
    enhance_scored_stocks,
    get_missing_critical_fields,
)


def minimal_scoring_config() -> dict:
    """Return a small scoring config for output/rejection tests."""
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
            "critical_missing_fields": [
                "source_symbol",
                "ticker",
                "name",
                "sector",
                "market_capitalization",
            ],
        },
        "ranking_policy": {
            "minimum_rankable_score": 50,
        },
    }


def sample_scoring_input() -> pd.DataFrame:
    """Return fake merged scoring input."""
    return pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "ticker": "AAPL",
                "name": "Apple Inc",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "market_capitalization": 3000000000000,
                "pe_ratio": 12,
                "revenue_growth_yoy": 0.10,
                "latest_net_margin": 0.22,
                "beta": 1.0,
            }
        ]
    )


def test_get_missing_critical_fields_returns_empty_when_present():
    config = minimal_scoring_config()
    row = sample_scoring_input().iloc[0]

    result = get_missing_critical_fields(row, config)

    assert result == []


def test_get_missing_critical_fields_identifies_missing_fields():
    config = minimal_scoring_config()
    row = pd.Series(
        {
            "source_symbol": "AAPL.US",
            "ticker": "AAPL",
            "name": "",
            "sector": None,
        }
    )

    result = get_missing_critical_fields(row, config)

    assert "name" in result
    assert "sector" in result
    assert "market_capitalization" in result


def test_build_metric_level_details_returns_one_row_per_metric():
    config = minimal_scoring_config()
    scoring_input = sample_scoring_input()

    result = build_metric_level_details(
        scoring_input=scoring_input,
        scoring_config=config,
    )

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 4
    assert set(result["category"]) == {"value", "growth", "quality", "stability"}
    assert set(result["metric_name"]) == {
        "pe_ratio",
        "revenue_growth_yoy",
        "latest_net_margin",
        "beta",
    }
    assert set(result["metric_status"]) == {"scored"}


def test_build_metric_level_details_handles_empty_input():
    config = minimal_scoring_config()

    result = build_metric_level_details(
        scoring_input=pd.DataFrame(),
        scoring_config=config,
    )

    assert isinstance(result, pd.DataFrame)
    assert result.empty
    assert "metric_name" in result.columns


def test_build_ranking_decision_returns_rankable_for_clean_high_score():
    config = minimal_scoring_config()

    scored_row = pd.Series(
        {
            "source_symbol": "AAPL.US",
            "final_score": 89,
            "missing_metric_count": 0,
            "score_confidence": "high",
        }
    )

    input_row = sample_scoring_input().iloc[0]

    result = build_ranking_decision(
        scored_row=scored_row,
        input_row=input_row,
        scoring_config=config,
    )

    assert result["ranking_status"] == "rankable"
    assert result["is_rankable"] is True
    assert result["rejection_reasons"] == ""
    assert result["watchlist_reasons"] == ""


def test_build_ranking_decision_rejects_missing_critical_fields():
    config = minimal_scoring_config()

    scored_row = pd.Series(
        {
            "source_symbol": "BAD.US",
            "final_score": 80,
            "missing_metric_count": 0,
            "score_confidence": "high",
        }
    )

    input_row = pd.Series(
        {
            "source_symbol": "BAD.US",
            "ticker": "BAD",
            "name": "",
            "sector": "",
            "market_capitalization": None,
        }
    )

    result = build_ranking_decision(
        scored_row=scored_row,
        input_row=input_row,
        scoring_config=config,
    )

    assert result["ranking_status"] == "rejected"
    assert result["is_rankable"] is False
    assert "critical_missing_fields" in result["rejection_reasons"]


def test_build_ranking_decision_watchlists_low_confidence():
    config = minimal_scoring_config()

    scored_row = pd.Series(
        {
            "source_symbol": "AAPL.US",
            "final_score": 70,
            "missing_metric_count": 3,
            "score_confidence": "low",
        }
    )

    input_row = sample_scoring_input().iloc[0]

    result = build_ranking_decision(
        scored_row=scored_row,
        input_row=input_row,
        scoring_config=config,
    )

    assert result["ranking_status"] == "watchlist"
    assert result["is_rankable"] is False
    assert "low_score_confidence" in result["watchlist_reasons"]
    assert "missing_metric_count:3" in result["watchlist_reasons"]


def test_build_ranking_decision_watchlists_low_score():
    config = minimal_scoring_config()

    scored_row = pd.Series(
        {
            "source_symbol": "AAPL.US",
            "final_score": 40,
            "missing_metric_count": 0,
            "score_confidence": "high",
        }
    )

    input_row = sample_scoring_input().iloc[0]

    result = build_ranking_decision(
        scored_row=scored_row,
        input_row=input_row,
        scoring_config=config,
    )

    assert result["ranking_status"] == "watchlist"
    assert result["is_rankable"] is False
    assert "final_score_below_50" in result["watchlist_reasons"]


def test_enhance_scored_stocks_adds_ranking_status():
    config = minimal_scoring_config()
    scoring_input = sample_scoring_input()

    scored_stocks = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "ticker": "AAPL",
                "name": "Apple Inc",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "final_score": 89,
                "missing_metric_count": 0,
                "score_confidence": "high",
                "scoring_notes": "",
            }
        ]
    )

    result = enhance_scored_stocks(
        scoring_input=scoring_input,
        scored_stocks=scored_stocks,
        scoring_config=config,
    )

    assert len(result) == 1
    assert result.loc[0, "ranking_status"] == "rankable"
    assert bool(result.loc[0, "is_rankable"]) is True
    assert result.loc[0, "score_summary"] == "89/100 (high confidence)"


def test_build_rejected_stocks_filters_rejected_rows():
    enhanced = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "ticker": "AAPL",
                "name": "Apple Inc",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "final_score": 89,
                "score_confidence": "high",
                "missing_metric_count": 0,
                "ranking_status": "rankable",
                "rejection_reasons": "",
                "watchlist_reasons": "",
                "scoring_notes": "",
            },
            {
                "source_symbol": "BAD.US",
                "ticker": "BAD",
                "name": "",
                "sector": "",
                "industry": "",
                "final_score": 80,
                "score_confidence": "high",
                "missing_metric_count": 0,
                "ranking_status": "rejected",
                "rejection_reasons": "critical_missing_fields:name,sector",
                "watchlist_reasons": "",
                "scoring_notes": "",
            },
        ]
    )

    result = build_rejected_stocks(enhanced)

    assert len(result) == 1
    assert result.iloc[0]["source_symbol"] == "BAD.US"
    assert result.iloc[0]["ranking_status"] == "rejected"


def test_build_scoring_outputs_returns_all_expected_outputs():
    config = minimal_scoring_config()

    normalized_metrics = pd.DataFrame(
        [
            {
                "source_symbol": "AAPL.US",
                "ticker": "AAPL",
                "name": "Apple Inc",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "market_capitalization": 3000000000000,
                "pe_ratio": 12,
                "beta": 1.0,
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

    result = build_scoring_outputs(
        normalized_metrics=normalized_metrics,
        financial_summary=financial_summary,
        scoring_config=config,
    )

    assert set(result.keys()) == {
        "all_scored_stocks",
        "scoring_metric_details",
        "rejected_stocks",
    }

    assert len(result["all_scored_stocks"]) == 1
    assert len(result["scoring_metric_details"]) == 4
    assert result["rejected_stocks"].empty
    assert result["all_scored_stocks"].iloc[0]["ranking_status"] == "rankable"