"""
Conservative valuation functions.

This module creates market-cap-based valuation ranges using:
- earnings power value
- free cash flow value
- sales multiple value

The goal is not precision. The goal is a cautious first-pass valuation range
with margin-of-safety labels and reliability flags.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


METHOD_PREFIXES = {
    "earnings_power_value": "earnings_value",
    "free_cash_flow_value": "fcf_value",
    "sales_multiple_value": "sales_value",
}


def load_valuation_config(config_path: Path) -> dict[str, Any]:
    """Load valuation configuration from YAML."""
    if not config_path.exists():
        raise FileNotFoundError(f"Valuation config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise TypeError("Valuation config must load as a dictionary.")

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


def merge_valuation_inputs(
    normalized_metrics: pd.DataFrame,
    financial_summary: pd.DataFrame,
    scored_stocks: pd.DataFrame,
) -> pd.DataFrame:
    """Merge normalized metrics, financial summary, and scoring output."""
    if normalized_metrics.empty:
        raise ValueError("normalized_metrics is empty.")

    if "source_symbol" not in normalized_metrics.columns:
        raise ValueError("normalized_metrics must include source_symbol.")

    valuation_input = normalized_metrics.copy()

    if not financial_summary.empty:
        if "source_symbol" not in financial_summary.columns:
            raise ValueError("financial_summary must include source_symbol.")

        valuation_input = valuation_input.merge(
            financial_summary,
            on="source_symbol",
            how="left",
            suffixes=("", "_financial_summary"),
        )

    if not scored_stocks.empty:
        if "source_symbol" not in scored_stocks.columns:
            raise ValueError("scored_stocks must include source_symbol.")

        scoring_columns = [
            column
            for column in [
                "source_symbol",
                "final_score",
                "score_confidence",
                "ranking_status",
                "is_rankable",
                "watchlist_reasons",
                "rejection_reasons",
            ]
            if column in scored_stocks.columns
        ]

        valuation_input = valuation_input.merge(
            scored_stocks[scoring_columns].drop_duplicates(
                subset=["source_symbol"]
            ),
            on="source_symbol",
            how="left",
            suffixes=("", "_scoring"),
        )

    return valuation_input


def get_sector_rule(
    row: pd.Series,
    valuation_config: dict[str, Any],
) -> tuple[str, str]:
    """Return sector valuation status and matching sector rule name."""
    sector_text = " ".join(
        str(row.get(column, ""))
        for column in ["sector", "industry"]
    ).lower()

    sector_rules = valuation_config.get("sector_rules", {})

    for rule_name, rule in sector_rules.items():
        keywords = rule.get("matching_keywords", [])
        for keyword in keywords:
            if str(keyword).lower() in sector_text:
                return rule.get("valuation_status", "allow"), rule_name

    return "allow", ""


def get_disabled_methods_for_sector(
    row: pd.Series,
    valuation_config: dict[str, Any],
) -> list[str]:
    """Return valuation methods disabled by sector rules."""
    _, rule_name = get_sector_rule(row=row, valuation_config=valuation_config)

    if not rule_name:
        return []

    sector_rule = valuation_config.get("sector_rules", {}).get(rule_name, {})

    return sector_rule.get("disabled_methods", [])


def calculate_multiple_range(
    input_value: float,
    multiples: dict[str, Any],
) -> dict[str, float]:
    """Calculate low/base/high value using configured multiples."""
    return {
        "low": input_value * float(multiples["low"]),
        "base": input_value * float(multiples["base"]),
        "high": input_value * float(multiples["high"]),
    }


def value_one_method(
    row: pd.Series,
    method_name: str,
    method_spec: dict[str, Any],
    disabled_methods: list[str],
) -> dict[str, Any]:
    """Run one valuation method for one company."""
    prefix = METHOD_PREFIXES.get(method_name, method_name)

    result = {
        "method_name": method_name,
        "prefix": prefix,
        "available": False,
        "low": None,
        "base": None,
        "high": None,
        "flags": [],
        "notes": [],
    }

    if not method_spec.get("enabled", True):
        result["flags"].append("method_disabled_in_config")
        return result

    if method_name in disabled_methods:
        result["flags"].append("method_disabled_by_sector_rule")
        return result

    input_field = method_spec["input_field"]
    input_value = safe_float(row.get(input_field))

    if input_value is None:
        result["flags"].append(f"missing_input:{input_field}")
        return result

    if input_value <= 0 and method_spec.get("rules", {}).get(
        "reject_method_if_input_nonpositive",
        True,
    ):
        result["flags"].append(f"nonpositive_input:{input_field}")
        return result

    value_range = calculate_multiple_range(
        input_value=input_value,
        multiples=method_spec["multiples"],
    )

    result["available"] = True
    result["low"] = value_range["low"]
    result["base"] = value_range["base"]
    result["high"] = value_range["high"]

    if method_name == "free_cash_flow_value":
        fcf_source = row.get("free_cash_flow_source")
        if is_missing(fcf_source) or str(fcf_source).lower() == "missing":
            result["flags"].append("free_cash_flow_source_missing")

        fcf_margin = safe_float(row.get("latest_fcf_margin"))
        if fcf_margin is not None and fcf_margin < 0:
            result["flags"].append("negative_fcf_margin")

    if method_name == "sales_multiple_value":
        net_margin = safe_float(row.get("latest_net_margin"))
        if net_margin is not None and net_margin < 0.05:
            result["flags"].append("low_net_margin_for_sales_multiple")

    return result


def combine_method_values(
    method_results: list[dict[str, Any]],
    valuation_config: dict[str, Any],
) -> dict[str, Any]:
    """Combine available valuation methods using configured weights."""
    methods_config = valuation_config.get("valuation_methods", {})

    available_results = [
        result for result in method_results if result["available"]
    ]

    if not available_results:
        return {
            "conservative_value_low": None,
            "conservative_value_base": None,
            "conservative_value_high": None,
            "methods_available": "",
            "methods_missing": ",".join(
                result["method_name"] for result in method_results
            ),
        }

    total_weight = sum(
        float(methods_config[result["method_name"]].get("weight", 0))
        for result in available_results
    )

    if total_weight == 0:
        total_weight = len(available_results)

    combined = {
        "low": 0.0,
        "base": 0.0,
        "high": 0.0,
    }

    for result in available_results:
        raw_weight = float(
            methods_config[result["method_name"]].get("weight", 1)
        )
        normalized_weight = raw_weight / total_weight

        combined["low"] += result["low"] * normalized_weight
        combined["base"] += result["base"] * normalized_weight
        combined["high"] += result["high"] * normalized_weight

    return {
        "conservative_value_low": combined["low"],
        "conservative_value_base": combined["base"],
        "conservative_value_high": combined["high"],
        "methods_available": ",".join(
            result["method_name"] for result in available_results
        ),
        "methods_missing": ",".join(
            result["method_name"]
            for result in method_results
            if not result["available"]
        ),
    }


def calculate_margin_of_safety(
    estimated_value: float | None,
    market_capitalization: float | None,
) -> float | None:
    """Calculate margin of safety relative to market capitalization."""
    if estimated_value is None or market_capitalization is None:
        return None

    if market_capitalization <= 0:
        return None

    return (estimated_value - market_capitalization) / market_capitalization


def label_margin_of_safety(
    margin_of_safety: float | None,
    valuation_config: dict[str, Any],
) -> str:
    """Label base margin of safety."""
    if margin_of_safety is None:
        return "not_available"

    thresholds = valuation_config.get("margin_of_safety", {}).get(
        "thresholds",
        {},
    )
    labels = valuation_config.get("margin_of_safety", {}).get("labels", {})

    if margin_of_safety >= float(thresholds.get("strong_discount", 0.30)):
        return labels.get("strong_discount", "potentially_undervalued")

    if margin_of_safety >= float(thresholds.get("moderate_discount", 0.15)):
        return labels.get("moderate_discount", "watchlist_discount")

    fair_lower = float(thresholds.get("fairly_valued_lower", -0.10))
    fair_upper = float(thresholds.get("fairly_valued_upper", 0.10))

    if fair_lower <= margin_of_safety <= fair_upper:
        return labels.get("fair", "roughly_fair_value")

    if margin_of_safety < float(thresholds.get("expensive", -0.10)):
        return labels.get("expensive", "potentially_overvalued")

    return "unclear"


def determine_valuation_confidence(
    method_results: list[dict[str, Any]],
    market_capitalization: float | None,
    score_confidence: str,
    valuation_status: str,
    valuation_flags: list[str],
) -> str:
    """Determine valuation confidence."""
    available_count = sum(result["available"] for result in method_results)

    if market_capitalization is None or market_capitalization <= 0:
        return "low"

    if valuation_status == "special_handling_required":
        return "low"

    if "low_score_confidence" in valuation_flags:
        return "low"

    if available_count >= 2 and score_confidence in {"high", "medium"}:
        return "high"

    if available_count >= 1:
        return "medium"

    return "low"


def build_valuation_row(
    row: pd.Series,
    valuation_config: dict[str, Any],
) -> dict[str, Any]:
    """Build one valuation output row."""
    market_cap = safe_float(row.get("market_capitalization"))
    valuation_status, sector_rule = get_sector_rule(
        row=row,
        valuation_config=valuation_config,
    )
    disabled_methods = get_disabled_methods_for_sector(
        row=row,
        valuation_config=valuation_config,
    )

    method_results = []

    for method_name, method_spec in valuation_config.get(
        "valuation_methods",
        {},
    ).items():
        method_results.append(
            value_one_method(
                row=row,
                method_name=method_name,
                method_spec=method_spec,
                disabled_methods=disabled_methods,
            )
        )

    combined = combine_method_values(
        method_results=method_results,
        valuation_config=valuation_config,
    )

    mos_low = calculate_margin_of_safety(
        estimated_value=combined["conservative_value_low"],
        market_capitalization=market_cap,
    )
    mos_base = calculate_margin_of_safety(
        estimated_value=combined["conservative_value_base"],
        market_capitalization=market_cap,
    )
    mos_high = calculate_margin_of_safety(
        estimated_value=combined["conservative_value_high"],
        market_capitalization=market_cap,
    )

    valuation_flags: list[str] = []

    if market_cap is None or market_cap <= 0:
        valuation_flags.append("market_cap_missing_or_nonpositive")

    if sector_rule:
        valuation_flags.append(f"sector_rule:{sector_rule}")

    score_confidence = str(row.get("score_confidence", "")).lower()
    if score_confidence == "low":
        valuation_flags.append("low_score_confidence")

    for result in method_results:
        valuation_flags.extend(result["flags"])

    valuation_confidence = determine_valuation_confidence(
        method_results=method_results,
        market_capitalization=market_cap,
        score_confidence=score_confidence,
        valuation_status=valuation_status,
        valuation_flags=valuation_flags,
    )

    output = {
        "source_symbol": row.get("source_symbol"),
        "ticker": row.get("ticker"),
        "name": row.get("name"),
        "sector": row.get("sector"),
        "industry": row.get("industry"),
        "market_capitalization": market_cap,
        "final_score": row.get("final_score"),
        "score_confidence": row.get("score_confidence"),
        "valuation_status": valuation_status,
        "valuation_confidence": valuation_confidence,
        "conservative_value_low": combined["conservative_value_low"],
        "conservative_value_base": combined["conservative_value_base"],
        "conservative_value_high": combined["conservative_value_high"],
        "margin_of_safety_low": mos_low,
        "margin_of_safety_base": mos_base,
        "margin_of_safety_high": mos_high,
        "margin_of_safety_label": label_margin_of_safety(
            margin_of_safety=mos_base,
            valuation_config=valuation_config,
        ),
        "methods_available": combined["methods_available"],
        "methods_missing": combined["methods_missing"],
        "valuation_flags": ";".join(sorted(set(valuation_flags))),
        "valuation_notes": "Market-cap-based MVP valuation range.",
    }

    for result in method_results:
        prefix = result["prefix"]
        output[f"{prefix}_low"] = result["low"]
        output[f"{prefix}_base"] = result["base"]
        output[f"{prefix}_high"] = result["high"]

    output_columns = valuation_config.get("output_columns", [])

    for column in output_columns:
        if column not in output:
            output[column] = None

    if output_columns:
        return {column: output.get(column) for column in output_columns}

    return output


def build_valuation_outputs(
    valuation_input: pd.DataFrame,
    valuation_config: dict[str, Any],
) -> pd.DataFrame:
    """Build valuation output rows for all companies."""
    if valuation_input.empty:
        return pd.DataFrame()

    rows = []

    for _, row in valuation_input.iterrows():
        rows.append(
            build_valuation_row(
                row=row,
                valuation_config=valuation_config,
            )
        )

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    return result.sort_values(
        by=["valuation_confidence", "margin_of_safety_base", "source_symbol"],
        ascending=[True, False, True],
    )