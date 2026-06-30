"""
Build a redacted EODHD API access report.

Inputs:
- .env
- config/eodhd_endpoint_config.yml

Output:
- outputs/api_access_report.csv

This script must never print or save API tokens.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

ENV_PATH = PROJECT_ROOT / ".env"
CONFIG_PATH = PROJECT_ROOT / "config" / "eodhd_endpoint_config.yml"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "api_access_report.csv"


def load_endpoint_config(config_path: Path) -> dict[str, Any]:
    """Load endpoint audit config."""
    if not config_path.exists():
        raise FileNotFoundError(f"Missing endpoint config: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise TypeError("Endpoint config must load as a dictionary.")

    return config


def mask_token(token: str | None) -> str:
    """Return a masked token label."""
    if not token:
        return "[MISSING]"
    if token == "demo":
        return "demo"
    if len(token) <= 8:
        return "[TOKEN_PRESENT]"
    return f"{token[:4]}...[REDACTED]...{token[-4:]}"


def redact_text(text: str, tokens: list[str | None]) -> str:
    """Redact any known token values from text."""
    redacted = text

    for token in tokens:
        if token and token != "demo":
            redacted = redacted.replace(token, "[REDACTED_API_TOKEN]")

    return redacted


def classify_response(status_code: int | None, text: str, json_data: Any) -> str:
    """Classify endpoint access result."""
    text_lower = (text or "").lower()

    if status_code is None:
        return "Unclear"

    if status_code == 200:
        if "error" in text_lower or "unauthorized" in text_lower:
            return "Unclear"
        return "Available"

    if status_code in {401, 403}:
        if any(word in text_lower for word in ["subscription", "plan", "not available", "not allowed", "only eod"]):
            return "Not available on my plan"
        return "Unauthorized or forbidden"

    if status_code in {400, 404}:
        return "Requires different URL/version or ticker formatting"

    if status_code >= 500:
        return "Server error or temporary issue"

    return "Unclear"


def summarize_json(json_data: Any) -> dict[str, Any]:
    """Summarize JSON shape without storing full payload."""
    if isinstance(json_data, dict):
        keys = list(json_data.keys())
        return {
            "json_type": "dict",
            "row_count": None,
            "top_level_fields_preview": ",".join(keys[:20]),
        }

    if isinstance(json_data, list):
        first_keys = []
        if json_data and isinstance(json_data[0], dict):
            first_keys = list(json_data[0].keys())

        return {
            "json_type": "list",
            "row_count": len(json_data),
            "top_level_fields_preview": ",".join(first_keys[:20]),
        }

    return {
        "json_type": type(json_data).__name__,
        "row_count": None,
        "top_level_fields_preview": "",
    }


def get_token_for_endpoint(
    token_source: str,
    api_token: str,
    fundamentals_token: str,
) -> str:
    """Select token for endpoint."""
    if token_source == "fundamentals_token":
        return fundamentals_token

    return api_token


def call_endpoint(
    endpoint: dict[str, Any],
    base_url: str,
    api_token: str,
    fundamentals_token: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Call one endpoint and return a redacted report row."""
    endpoint_name = endpoint["name"]
    enabled = bool(endpoint.get("enabled", True))

    if not enabled:
        return {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint_name": endpoint_name,
            "enabled": False,
            "token_source": endpoint.get("token_source"),
            "token_used_masked": "",
            "url_path": endpoint.get("path"),
            "http_status": None,
            "classification": "Skipped",
            "json_type": "",
            "row_count": None,
            "top_level_fields_preview": "",
            "error_preview": "",
        }

    token_source = endpoint.get("token_source", "api_token")
    token = get_token_for_endpoint(
        token_source=token_source,
        api_token=api_token,
        fundamentals_token=fundamentals_token,
    )

    url = base_url.rstrip("/") + endpoint["path"]
    params = dict(endpoint.get("params", {}))
    params["api_token"] = token

    tokens_to_redact = [api_token, fundamentals_token]

    try:
        response = requests.get(url, params=params, timeout=timeout_seconds)
        text_preview = redact_text(response.text[:500], tokens_to_redact)

        try:
            json_data = response.json()
        except Exception:
            json_data = None

        json_summary = summarize_json(json_data)

        classification = classify_response(
            status_code=response.status_code,
            text=text_preview,
            json_data=json_data,
        )

        return {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint_name": endpoint_name,
            "enabled": True,
            "token_source": token_source,
            "token_used_masked": mask_token(token),
            "url_path": endpoint.get("path"),
            "http_status": response.status_code,
            "classification": classification,
            "json_type": json_summary["json_type"],
            "row_count": json_summary["row_count"],
            "top_level_fields_preview": json_summary["top_level_fields_preview"],
            "error_preview": "" if classification == "Available" else text_preview,
        }

    except requests.RequestException as exc:
        return {
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint_name": endpoint_name,
            "enabled": True,
            "token_source": token_source,
            "token_used_masked": mask_token(token),
            "url_path": endpoint.get("path"),
            "http_status": None,
            "classification": "Unclear",
            "json_type": "",
            "row_count": None,
            "top_level_fields_preview": "",
            "error_preview": redact_text(str(exc), tokens_to_redact),
        }


def main() -> None:
    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f"Missing .env file: {ENV_PATH}\n"
            "Expected EODHD_API_TOKEN and optionally EODHD_FUNDAMENTALS_TOKEN."
        )

    load_dotenv(dotenv_path=ENV_PATH)

    api_token = os.getenv("EODHD_API_TOKEN")
    fundamentals_token = os.getenv("EODHD_FUNDAMENTALS_TOKEN", api_token)

    if not api_token:
        raise ValueError("Missing EODHD_API_TOKEN in .env.")

    if not fundamentals_token:
        raise ValueError("Missing EODHD_FUNDAMENTALS_TOKEN and EODHD_API_TOKEN fallback.")

    config = load_endpoint_config(CONFIG_PATH)
    defaults = config.get("defaults", {})

    base_url = defaults.get("base_url", "https://eodhd.com")
    timeout_seconds = int(defaults.get("timeout_seconds", 30))

    endpoints = config.get("endpoints", [])

    if not endpoints:
        raise ValueError("No endpoints configured.")

    print("Building EODHD API access report...")
    print(f"Config: {CONFIG_PATH}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"EODHD_API_TOKEN: {mask_token(api_token)}")
    print(f"EODHD_FUNDAMENTALS_TOKEN: {mask_token(fundamentals_token)}")
    print("No full tokens will be printed or saved.")

    rows = []

    for endpoint in endpoints:
        print(f"Checking: {endpoint['name']}")
        rows.append(
            call_endpoint(
                endpoint=endpoint,
                base_url=base_url,
                api_token=api_token,
                fundamentals_token=fundamentals_token,
                timeout_seconds=timeout_seconds,
            )
        )

    report = pd.DataFrame(rows)
    report.to_csv(OUTPUT_PATH, index=False)

    print(f"\nAPI access report saved to: {OUTPUT_PATH}")
    print("\nClassification counts:")
    print(report["classification"].value_counts(dropna=False).to_string())

    print("\nEndpoint summary:")
    print(
        report[
            [
                "endpoint_name",
                "enabled",
                "token_source",
                "http_status",
                "classification",
                "json_type",
                "row_count",
                "top_level_fields_preview",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()