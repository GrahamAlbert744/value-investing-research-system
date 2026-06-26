"""
Reusable EODHD API client.

Supports:
- Personal token for EOD price data
- Demo or paid token for Fundamentals data
- Exchange symbol metadata for universe validation
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
    """Small reusable client for EODHD API calls."""

    api_token: str
    fundamentals_token: str | None = None
    base_url: str = "https://eodhd.com/api"
    fundamentals_base_url: str = "https://eodhd.com/api/v1.1"
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "EODHDClient":
        """Create an EODHD client using credentials from local .env."""
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
        """Redact real API tokens from text before errors are shown."""
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
        """Internal helper for GET requests with safe error handling."""
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
        """
        Get historical end-of-day prices for one ticker.

        Example:
        AAPL.US
        """
        url = f"{self.base_url}/eod/{symbol}"

        data = self._get_json(
            url=url,
            params={
                "api_token": self.api_token,
                "fmt": "json",
            },
        )

        if not isinstance(data, list):
            raise TypeError(
                f"Expected list from EOD endpoint, got {type(data).__name__}"
            )

        return data

    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        """
        Get fundamentals JSON for one ticker.

        Uses EODHD_FUNDAMENTALS_TOKEN if present.
        This allows demo fundamentals for AAPL.US while your personal token
        is limited to EOD price data.
        """
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

    def get_exchange_symbols(
        self,
        exchange_code: str = "US",
        security_type: str | None = "common_stock",
        include_delisted: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Get symbol metadata for one EODHD exchange.

        Example:
        exchange_code="US"
        security_type="common_stock"

        EODHD endpoint:
        /exchange-symbol-list/{EXCHANGE_CODE}
        """
        url = f"{self.base_url}/exchange-symbol-list/{exchange_code}"

        params: dict[str, Any] = {
            "api_token": self.api_token,
            "fmt": "json",
        }

        if security_type:
            params["type"] = security_type

        if include_delisted:
            params["delisted"] = "1"

        data = self._get_json(
            url=url,
            params=params,
        )

        if not isinstance(data, list):
            raise TypeError(
                "Expected list from exchange-symbol-list endpoint, "
                f"got {type(data).__name__}"
            )

        return data