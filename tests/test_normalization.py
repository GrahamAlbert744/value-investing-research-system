"""
Tests for EODHD fundamentals normalization.

These tests use tiny fake dictionaries so they do not require:
- API access
- .env
- raw JSON files
"""

from pathlib import Path

import pytest
import yaml

from src.normalization import (
    get_nested_value,
    load_field_mapping,
    normalize_fundamentals,
    summarize_missing_values,
)


def test_get_nested_value_returns_existing_value():
    data = {
        "General": {
            "Name": "Apple Inc",
            "Sector": "Technology",
        }
    }

    result = get_nested_value(data, "General.Name")

    assert result == "Apple Inc"


def test_get_nested_value_returns_none_for_missing_path():
    data = {
        "General": {
            "Name": "Apple Inc",
        }
    }

    result = get_nested_value(data, "General.Industry")

    assert result is None


def test_normalize_fundamentals_creates_flat_row():
    data = {
        "General": {
            "Code": "AAPL",
            "Name": "Apple Inc",
            "Sector": "Technology",
        },
        "Highlights": {
            "MarketCapitalization": 3000000000000,
            "PERatio": 30.5,
        },
    }

    field_mapping = {
        "mapped_fields": {
            "ticker": {
                "raw_path": "General.Code",
            },
            "name": {
                "raw_path": "General.Name",
            },
            "sector": {
                "raw_path": "General.Sector",
            },
            "market_capitalization": {
                "raw_path": "Highlights.MarketCapitalization",
            },
            "pe_ratio": {
                "raw_path": "Highlights.PERatio",
            },
        }
    }

    row = normalize_fundamentals(
        data=data,
        field_mapping=field_mapping,
        source_symbol="AAPL.US",
    )

    assert row["source_symbol"] == "AAPL.US"
    assert row["ticker"] == "AAPL"
    assert row["name"] == "Apple Inc"
    assert row["sector"] == "Technology"
    assert row["market_capitalization"] == 3000000000000
    assert row["pe_ratio"] == 30.5
    assert "normalized_at_utc" in row


def test_summarize_missing_values_counts_missing_fields():
    row = {
        "ticker": "AAPL",
        "name": "Apple Inc",
        "sector": None,
        "industry": "",
    }

    summary = summarize_missing_values(row)

    assert summary["total_fields"] == 4
    assert summary["missing_fields"] == 2
    assert summary["non_missing_fields"] == 2


def test_load_field_mapping_reads_yaml(tmp_path: Path):
    mapping_path = tmp_path / "field_mapping.yml"

    mapping = {
        "mapped_fields": {
            "ticker": {
                "raw_path": "General.Code",
            }
        }
    }

    with mapping_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(mapping, file)

    loaded = load_field_mapping(mapping_path)

    assert loaded["mapped_fields"]["ticker"]["raw_path"] == "General.Code"


def test_load_field_mapping_missing_file_raises_error(tmp_path: Path):
    missing_path = tmp_path / "missing_field_mapping.yml"

    with pytest.raises(FileNotFoundError):
        load_field_mapping(missing_path)