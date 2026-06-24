"""
Inspect top-level fields from EODHD Fundamentals data.

This script:
- Uses EODHD_FUNDAMENTALS_TOKEN from .env
- Allows demo token for AAPL.US fundamentals exploration
- Saves raw JSON locally
- Prints top-level fields
- Does not print full tokens
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.eodhd_client import EODHDClient


def main() -> None:
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)

    symbol = os.getenv("EODHD_TEST_SYMBOL", "AAPL.US")
    fundamentals_token = os.getenv("EODHD_FUNDAMENTALS_TOKEN")

    if not fundamentals_token:
        raise ValueError(
            "Missing EODHD_FUNDAMENTALS_TOKEN in .env.\n"
            "For now, add:\n"
            "EODHD_FUNDAMENTALS_TOKEN=demo"
        )

    client = EODHDClient.from_env()

    output_dir = PROJECT_ROOT / "outputs" / "raw_samples"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_symbol = symbol.replace(".", "_")
    output_path = output_dir / f"fundamentals_{safe_symbol}_{timestamp}.json"

    print(f"Requesting EODHD fundamentals for: {symbol}")
    print("Using EODHD_FUNDAMENTALS_TOKEN from .env")
    print(f"Fundamentals token is demo: {fundamentals_token == 'demo'}")

    data = client.get_fundamentals(symbol=symbol)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    saved_text = output_path.read_text(encoding="utf-8")

    if fundamentals_token != "demo" and fundamentals_token in saved_text:
        raise RuntimeError("Security failure: token appeared in saved JSON.")

    print(f"\nRaw JSON saved to: {output_path}")
    print("API token found in saved JSON: no")

    print("\nTop-level EODHD fields:")
    for field in sorted(data.keys()):
        print(f"- {field}")


if __name__ == "__main__":
    main()