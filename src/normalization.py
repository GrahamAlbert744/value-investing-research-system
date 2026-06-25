"""
Normalize EODHD fundamentals JSON into a flat company-level metrics row.

This module:
- Reads config/field_mapping.yml
- Extracts mapped fields from raw EODHD JSON
- Produces one clean dictionary suitable for CSV/database storage
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


def normalize_fundamentals(
    data: dict[str, Any],
    field_mapping: dict[str, Any],
    source_symbol: str | None = None,
) -> dict[str, Any]:
    """
    Normalize one EODHD fundamentals JSON response into one flat row.
    """
    mapped_fields = field_mapping.get("mapped_fields", {})

    if not isinstance(mapped_fields, dict):
        raise TypeError("field_mapping.yml must contain a mapped_fields dictionary.")

    row: dict[str, Any] = {
        "source_symbol": source_symbol,
        "normalized_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    for normalized_name, spec in mapped_fields.items():
        raw_path = spec.get("raw_path")
        row[normalized_name] = get_nested_value(data=data, raw_path=raw_path)

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