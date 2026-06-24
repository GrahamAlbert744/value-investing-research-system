"""
Reusable EODHD API client.

This module:
- Loads EODHD credentials from .env
- Uses the recommended v1.1 fundamentals endpoint by default
- Returns JSON data
- Avoids printing or saving the API token
- Sanitizes API errors so the token does not appear in tracebacks
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
    base_url: str = "https://eodhd.com/api/v1.1"
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "EODHDClient":
        """Create an EODHD client using credentials from local .env."""
        load_dotenv()

        api_token = os.getenv("EODHD_API_TOKEN")
        base_url = os.getenv("EODHD_BASE_URL", "https://eodhd.com/api/v1.1")

        if not api_token:
            raise ValueError(
                "Missing EODHD_API_TOKEN. Add it to your local .env file."
            )

        return cls(api_token=api_token, base_url=base_url)

    def _redact(self, text: str) -> str:
        """Redact the API token from any text."""
        return text.replace(self.api_token, "[REDACTED_API_TOKEN]")

    def _get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Internal helper for safe EODHD GET requests."""
        if params is None:
            params = {}

        request_params = {
            **params,
            "api_token": self.api_token,
            "fmt": "json",
        }

        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        response = requests.get(
            url,
            params=request_params,
            timeout=self.timeout,
        )

        if response.status_code >= 400:
            safe_url = self._redact(response.url)
            safe_response_preview = self._redact(response.text[:500])

            raise RuntimeError(
                "EODHD request failed.\n"
                f"Status code: {response.status_code}\n"
                f"URL: {safe_url}\n"
                f"Response preview: {safe_response_preview}"
            )

        data = response.json()

        if not isinstance(data, dict):
            raise TypeError(
                f"Expected dictionary response from EODHD, got {type(data).__name__}"
            )

        return data

    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        """
        Get fundamentals JSON for one ticker.

        Example:
        AAPL.US
        """
        return self._get_json(f"fundamentals/{symbol}")