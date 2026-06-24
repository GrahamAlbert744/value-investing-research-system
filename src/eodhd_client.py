"""
Reusable EODHD API client.

Supports:
- Personal token for EOD price data
- Demo or paid token for Fundamentals data
- Safe error handling that redacts tokens
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv


@dataclass
class EODHDClient:
    api_token: str
    fundamentals_token: str | None = None
    base_url: str = "https://eodhd.com/api"
    fundamentals_base_url: str = "https://eodhd.com/api/v1.1"
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "EODHDClient":
        load_dotenv()

        api_token = os.getenv("EODHD_API_TOKEN")
        fundamentals_token = os.getenv("EODHD_FUNDAMENTALS_TOKEN", api_token)

        if not api_token:
            raise ValueError("Missing EODHD_API_TOKEN in local .env file.")

        return cls(
            api_token=api_token,
            fundamentals_token=fundamentals_token,
        )

    def _redact(self, text: str) -> str:
        tokens_to_redact = [
            self.api_token,
            self.fundamentals_token,
        ]

        redacted = text

        for token in tokens_to_redact:
            if token and token != "demo":
                redacted = redacted.replace(token, "[REDACTED_API_TOKEN]")

        return redacted

    def _get_json(
        self,
        url: str,
        params: dict[str, Any],
    ) -> Any:
        response = requests.get(url, params=params, timeout=self.timeout)

        if response.status_code >= 400:
            safe_url = self._redact(response.url)
            safe_preview = self._redact(response.text[:500])

            raise RuntimeError(
                "EODHD request failed.\n"
                f"Status code: {response.status_code}\n"
                f"URL: {safe_url}\n"
                f"Response preview: {safe_preview}"
            )

        return response.json()

    def get_eod_prices(self, symbol: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/eod/{symbol}"

        data = self._get_json(
            url=url,
            params={
                "api_token": self.api_token,
                "fmt": "json",
            },
        )

        if not isinstance(data, list):
            raise TypeError(f"Expected list from EOD endpoint, got {type(data).__name__}")

        return data

    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        url = f"{self.fundamentals_base_url}/fundamentals/{symbol}"

        token = self.fundamentals_token or self.api_token

        data = self._get_json(
            url=url,
            params={
                "api_token": token,
                "fmt": "json",
            },
        )

        if not isinstance(data, dict):
            raise TypeError(
                f"Expected dict from Fundamentals endpoint, got {type(data).__name__}"
            )

        return data