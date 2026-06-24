"""
Inspect top-level fields from EODHD fundamentals data.

This script:
1. Loads EODHD credentials from local .env through EODHDClient.
2. Requests fundamentals data for one test symbol.
3. Saves raw JSON to outputs/raw_samples/.
4. Confirms the API token was not saved.
5. Prints top-level fields in the terminal.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from src.eodhd_client import EODHDClient


def main() -> None:
    load_dotenv()

    symbol = os.getenv("EODHD_TEST_SYMBOL", "AAPL.US")

    client = EODHDClient.from_env()

    output_dir = Path("outputs/raw_samples")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_symbol = symbol.replace(".", "_")
    output_path = output_dir / f"fundamentals_{safe_symbol}_{timestamp}.json"

    print(f"Requesting EODHD fundamentals for: {symbol}")
    print("API token loaded from .env: yes")

    data = client.get_fundamentals(symbol=symbol)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    saved_text = output_path.read_text(encoding="utf-8")

    if client.api_token in saved_text:
        raise RuntimeError(
            "Security failure: API token appeared in saved JSON file."
        )

    print(f"\nRaw JSON saved to: {output_path}")
    print("API token found in saved JSON: no")

    top_level_fields = sorted(data.keys())

    print("\nTop-level EODHD fields:")
    for field in top_level_fields:
        print(f"- {field}")


if __name__ == "__main__":
    main()