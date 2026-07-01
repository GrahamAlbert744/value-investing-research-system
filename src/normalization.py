"""
Normalize EODHD fundamentals JSON into a flat company-level metrics row.

Supports both:
- raw_path: single EODHD path
- raw_paths: ordered fallback EODHD paths

This keeps field mapping flexible when EODHD fields differ across companies,
security types, or endpoint versions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def load_field_mapping(mapping_path: Path) -> dict[str, Any]:
    """Load field mapping YAML."""
    if not mapping_path.exists():
        raise FileNotFoundError(f"Field mapping file not found: {mapping_path}")

    with mapping_path.open("r", encoding="utf-8") as file:
        mapping = yaml.safe_load(file)

    if not isinstance(mapping, dict):
        raise TypeError("Field mapping must load as a dictionary.")

    return mapping


def get_nested_value(data: dict[str, Any], raw_path: str | None) -> Any:
    """
    Get a value from nested JSON using dot-separated paths.

    Example:
    raw_path = "General.Name"
    """
    if not raw_path:
        return None

    current: Any = data

    for part in raw_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


def get_candidate_paths(spec: dict[str, Any]) -> list[str]:
    """
    Return ordered raw paths from a mapping spec.

    Backward compatible:
    - old style: raw_path: "General.Code"
    - new style: raw_paths: ["General.PrimaryTicker", "General.Code"]
    """
    raw_paths = spec.get("raw_paths")

    if isinstance(raw_paths, list):
        return [str(path) for path in raw_paths if path]

    raw_path = spec.get("raw_path")

    if raw_path:
        return [str(raw_path)]

    return []


def get_first_available_value(
    data: dict[str, Any],
    candidate_paths: list[str],
) -> tuple[Any, str | None]:
    """
    Return the first non-missing value from candidate paths.

    Returns:
    - value
    - raw path used
    """
    for raw_path in candidate_paths:
        value = get_nested_value(data=data, raw_path=raw_path)

        if value is not None and value != "":
            return value, raw_path

    return None, None


def normalize_fundamentals(
    data: dict[str, Any],
    field_mapping: dict[str, Any],
    source_symbol: str | None = None,
    include_source_paths: bool = False,
) -> dict[str, Any]:
    """
    Normalize one EODHD fundamentals JSON response into one flat row.

    If include_source_paths=True, also add:
    - <normalized_field>__source_path
    """
    mapped_fields = field_mapping.get("mapped_fields", {})

    if not isinstance(mapped_fields, dict):
        raise TypeError("field_mapping.yml must contain a mapped_fields dictionary.")

    row: dict[str, Any] = {
        "source_symbol": source_symbol,
        "normalized_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    for normalized_name, spec in mapped_fields.items():
        if not isinstance(spec, dict):
            raise TypeError(
                f"Mapping spec for {normalized_name} must be a dictionary."
            )

        candidate_paths = get_candidate_paths(spec)
        value, source_path = get_first_available_value(
            data=data,
            candidate_paths=candidate_paths,
        )

        row[normalized_name] = value

        if include_source_paths:
            row[f"{normalized_name}__source_path"] = source_path

    return row


def summarize_missing_values(row: dict[str, Any]) -> dict[str, int]:
    """Create a simple summary of missing values in a normalized row."""
    total_fields = len(row)
    missing_fields = sum(value is None or value == "" for value in row.values())

    return {
        "total_fields": total_fields,
        "missing_fields": missing_fields,
        "non_missing_fields": total_fields - missing_fields,
    }