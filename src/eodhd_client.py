"""
Reusable EODHD API client.

This module is intentionally small at this stage.
Goal:
- Load EODHD credentials from .env
- Call the fundamentals endpoint
- Return JSON data
- Never expose or save the API token
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv


@dataclass
class EODHDClient:
    """Small client for EODHD API calls."""

    api_token: str
    base_url: str = "https://eodhd.com/api"
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "EODHDClient":
        """Create client using values from local .env file."""
        load_dotenv()

        api_token = os.getenv("EODHD_API_TOKEN")
        base_url = os.getenv("EODHD_BASE_URL", "https://eodhd.com/api")

        if not api_token:
            raise ValueError(
                "Missing EODHD_API_TOKEN. Add it to your local .env file."
            )

        return cls(api_token=api_token, base_url=base_url)

    def get_fundamentals(self, symbol: str) -> dict[str, Any]:
        """
        Get fundamentals JSON for one symbol.

        Example symbol:
        AAPL.US
        """
        url = f"{self.base_url}/fundamentals/{symbol}"

        params = {
            "api_token": self.api_token,
            "fmt": "json",
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise TypeError(
                f"Expected dictionary response from EODHD, got {type(data).__name__}"
            )

        return data