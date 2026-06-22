import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv


load_dotenv()


class EODHDClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("6a345aab83c1e8.67490950")

        if not self.api_key:
            raise ValueError("Missing EODHD_API_KEY. Add it to your .env file.")

        self.base_url = "https://eodhd.com/api"

    def _request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        params["api_token"] = self.api_key
        params["fmt"] = "json"

        url = f"{self.base_url}/{endpoint}"

        response = requests.get(url, params=params, timeout=30)

        metadata = {
            "endpoint": endpoint,
            "params_without_token": {k: v for k, v in params.items() if k != "api_token"},
            "status_code": response.status_code,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "url_without_token": response.url.split("api_token=")[0] + "api_token=REDACTED",
        }

        try:
            data = response.json()
        except json.JSONDecodeError:
            data = {
                "error": "Invalid JSON response",
                "text_preview": response.text[:500],
            }

        return {
            "metadata": metadata,
            "data": data,
        }

    def get_fundamentals_section(self, ticker: str, section: str) -> Dict[str, Any]:
        endpoint = f"fundamentals/{ticker}"
        return self._request(endpoint, params={"filter": section})

    def get_eod_prices(self, ticker: str, from_date: Optional[str] = None, to_date: Optional[str] = None):
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        endpoint = f"eod/{ticker}"
        return self._request(endpoint, params=params)


def payload_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
