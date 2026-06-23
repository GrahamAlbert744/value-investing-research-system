"""
EODHD API client.

MVP purpose:
- Pull filtered fundamentals sections for a single ticker.
- Keep this small and readable while we learn the EODHD data structure.
"""

import os
from typing import Any

import requests
from dotenv import load_dotenv


load_dotenv()


class EODHDClient:
    """Small EODHD API client for filtered fundamentals requests."""

    def __init__(self, api_token: str | None = None, timeout: int = 30):
        self.api_token = api_token or os.getenv("6a345aab83c1e8.67490950") or "demo"
        self.timeout = timeout
        self.base_url = "https://eodhd.com/api"

    def get_fundamentals_section(self, ticker: str, section: str) -> dict[str, Any]:
        """
        Fetch one filtered fundamentals section for a ticker.

        Example:
            client.get_fundamentals_section("AAPL.US", "General")
        """
        url = f"{self.base_url}/fundamentals/{ticker}"
        params = {
            "api_token": self.api_token,
            "fmt": "json",
            "filter": section,
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise ValueError(
                f"Expected dict response for {ticker} {section}, got {type(data)}"
            )

        return data