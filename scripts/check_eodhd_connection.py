"""
Check that the project can connect to EODHD.

IMPORTANT:
Do not put your real API key in this script.

Put your API key in a local .env file in the project root:

    EODHD_API_TOKEN=PASTE_YOUR_REAL_EODHD_API_KEY_HERE
    EODHD_BASE_URL=https://eodhd.com/api
    EODHD_TEST_SYMBOL=AAPL.US

This script confirms:
- .env exists and is loaded
- EODHD_API_TOKEN exists
- EODHDClient imports
- EODHD fundamentals call succeeds
- top-level fields are visible
- token is not printed
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


# Ensure Python can import from the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.eodhd_client import EODHDClient


def mask_token(token: str) -> str:
    """Show that a token exists without exposing it."""
    if len(token) <= 8:
        return "[TOKEN_PRESENT_BUT_TOO_SHORT_TO_MASK]"
    return f"{token[:4]}...[REDACTED]...{token[-4:]}"


def main() -> None:
    env_path = PROJECT_ROOT / ".env"

    if not env_path.exists():
        raise FileNotFoundError(
            f"No .env file found at: {env_path}\n\n"
            "Create one with:\n"
            "EODHD_API_TOKEN=PASTE_YOUR_REAL_EODHD_API_KEY_HERE\n"
            "EODHD_BASE_URL=https://eodhd.com/api\n"
            "EODHD_TEST_SYMBOL=AAPL.US\n"
        )

    load_dotenv(dotenv_path=env_path)

    token = os.getenv("EODHD_API_TOKEN")
    base_url = os.getenv("EODHD_BASE_URL", "https://eodhd.com/api")
    symbol = os.getenv("EODHD_TEST_SYMBOL", "AAPL.US")

    if not token:
        raise ValueError(
            "EODHD_API_TOKEN is missing from your local .env file.\n\n"
            "Open .env and add:\n"
            "EODHD_API_TOKEN=PASTE_YOUR_REAL_EODHD_API_KEY_HERE\n"
        )

    if "PASTE_YOUR_REAL" in token or "YOUR_REAL" in token:
        raise ValueError(
            "Your .env still contains the placeholder text.\n"
            "Replace PASTE_YOUR_REAL_EODHD_API_KEY_HERE with your actual EODHD API key."
        )

    print("Project root:", PROJECT_ROOT)
    print(".env file found: yes")
    print("Local .env loaded: yes")
    print("EODHD_API_TOKEN present: yes")
    print("Masked token:", mask_token(token))
    print("Base URL:", base_url)
    print("Test symbol:", symbol)

    client = EODHDClient(
        api_token=token,
        base_url=base_url,
    )

    data = client.get_fundamentals(symbol)

    print("\nEODHD API call succeeded: yes")

    if isinstance(data, dict):
        fields = sorted(data.keys())
        print("\nTop-level EODHD fields:")
        for field in fields:
            print(f"- {field}")
    else:
        raise TypeError(f"Unexpected EODHD response type: {type(data).__name__}")


if __name__ == "__main__":
    main()