"""
Diagnostic EODHD connection check.

Purpose:
- Confirm .env exists
- Confirm EODHD_API_TOKEN is loaded
- Test whether the token is valid
- Test whether basic End-of-Day data works
- Test whether Fundamentals works with demo
- Test whether Fundamentals works with your personal token
- Avoid printing the full API token

Do NOT put your real API key in this script.

Put your key in .env:

    EODHD_API_TOKEN=YOUR_REAL_EODHD_TOKEN_HERE
    EODHD_TEST_SYMBOL=AAPL.US
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

ENV_PATH = PROJECT_ROOT / ".env"


def mask_token(token: str) -> str:
    """Show that a token exists without exposing it."""
    if not token:
        return "[MISSING]"
    if len(token) <= 8:
        return "[TOKEN_PRESENT_BUT_TOO_SHORT_TO_MASK]"
    return f"{token[:4]}...[REDACTED]...{token[-4:]}"


def safe_get_json(url: str, params: dict[str, Any], token: str) -> dict[str, Any]:
    """
    Make a GET request and return diagnostic information.

    This function does NOT raise HTTPError, because those tracebacks can expose tokens.
    """
    try:
        response = requests.get(url, params=params, timeout=30)

        safe_url = response.url.replace(token, "[REDACTED_API_TOKEN]")

        result = {
            "ok": response.ok,
            "status_code": response.status_code,
            "url": safe_url,
            "content_type": response.headers.get("Content-Type", ""),
            "text_preview": response.text[:400].replace(token, "[REDACTED_API_TOKEN]"),
            "json": None,
        }

        try:
            result["json"] = response.json()
        except Exception:
            result["json"] = None

        return result

    except requests.RequestException as exc:
        return {
            "ok": False,
            "status_code": None,
            "url": url.replace(token, "[REDACTED_API_TOKEN]"),
            "content_type": "",
            "text_preview": str(exc).replace(token, "[REDACTED_API_TOKEN]"),
            "json": None,
        }


def print_result(label: str, result: dict[str, Any]) -> None:
    """Print one test result safely."""
    print(f"\n--- {label} ---")
    print(f"Success: {result['ok']}")
    print(f"Status code: {result['status_code']}")
    print(f"URL: {result['url']}")

    if result["ok"]:
        data = result["json"]
        if isinstance(data, dict):
            print("JSON type: dict")
            print("Top-level fields:")
            for field in sorted(data.keys())[:30]:
                print(f"- {field}")
        elif isinstance(data, list):
            print("JSON type: list")
            print(f"Rows returned: {len(data)}")
            if data and isinstance(data[0], dict):
                print("First row fields:")
                for field in sorted(data[0].keys())[:30]:
                    print(f"- {field}")
        else:
            print("JSON type: unavailable or unexpected")
    else:
        print("Response preview:")
        print(result["text_preview"])


def main() -> None:
    if not ENV_PATH.exists():
        raise FileNotFoundError(
            f"No .env file found at: {ENV_PATH}\n"
            "Create .env with:\n"
            "EODHD_API_TOKEN=YOUR_REAL_EODHD_TOKEN_HERE\n"
            "EODHD_TEST_SYMBOL=AAPL.US\n"
        )

    load_dotenv(dotenv_path=ENV_PATH)

    token = os.getenv("EODHD_API_TOKEN")
    symbol = os.getenv("EODHD_TEST_SYMBOL", "AAPL.US")

    if not token:
        raise ValueError(
            "EODHD_API_TOKEN is missing from .env.\n"
            "Open .env and add:\n"
            "EODHD_API_TOKEN=YOUR_REAL_EODHD_TOKEN_HERE\n"
        )

    if "YOUR_REAL" in token or "PASTE" in token:
        raise ValueError(
            "Your .env still appears to contain placeholder text. "
            "Replace it with your actual EODHD token."
        )

    print("Project root:", PROJECT_ROOT)
    print(".env file found: yes")
    print("Local .env loaded: yes")
    print("EODHD_API_TOKEN present: yes")
    print("Masked token:", mask_token(token))
    print("Test symbol:", symbol)

    # 1. Test whether your token is valid at all.
    user_result = safe_get_json(
        url="https://eodhd.com/api/user",
        params={"api_token": token, "fmt": "json"},
        token=token,
    )
    print_result("User API token validity test", user_result)

    # 2. Test basic End-of-Day endpoint with your personal token.
    eod_result = safe_get_json(
        url=f"https://eodhd.com/api/eod/{symbol}",
        params={"api_token": token, "fmt": "json"},
        token=token,
    )
    print_result("Personal token EOD price test", eod_result)

    # 3. Test Fundamentals with demo token.
    demo_fundamentals_result = safe_get_json(
        url=f"https://eodhd.com/api/v1.1/fundamentals/{symbol}",
        params={"api_token": "demo", "fmt": "json"},
        token=token,
    )
    print_result("Demo token Fundamentals test", demo_fundamentals_result)

    # 4. Test Fundamentals with your personal token.
    personal_fundamentals_result = safe_get_json(
        url=f"https://eodhd.com/api/v1.1/fundamentals/{symbol}",
        params={"api_token": token, "fmt": "json"},
        token=token,
    )
    print_result("Personal token Fundamentals test", personal_fundamentals_result)

    print("\n=== Diagnosis ===")

    if user_result["ok"] and eod_result["ok"] and not personal_fundamentals_result["ok"]:
        print(
            "Your token appears valid, and basic EOD data works, "
            "but Fundamentals access failed. This likely means your plan/key "
            "does not include Fundamentals access."
        )
    elif not user_result["ok"]:
        print(
            "Your token may be invalid, expired, copied incorrectly, or not active. "
            "Regenerate it in the EODHD dashboard and update .env."
        )
    elif personal_fundamentals_result["ok"]:
        print(
            "Your token works for Fundamentals. The EODHD connection is ready."
        )
    else:
        print(
            "Mixed result. Review the status codes above. If Fundamentals is 403, "
            "check EODHD plan permissions."
        )


if __name__ == "__main__":
    main()