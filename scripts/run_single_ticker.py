"""
Run a single-ticker EODHD fundamentals pull.

MVP purpose:
- Pull a small set of filtered EODHD fundamentals sections.
- Save raw JSON responses locally.
- This helps us inspect actual EODHD fields before building scoring/database logic.

Example:
    python scripts/run_single_ticker.py --ticker AAPL.US
"""

import argparse
import json
import sys
from pathlib import Path


# Allow running this script from the project root without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.eodhd_client import EODHDClient  # noqa: E402


SECTIONS = [
    "General",
    "Highlights",
    "Valuation",
    "SharesStats",
    "SplitsDividends",
]


def save_json(data: dict, path: Path) -> None:
    """Save a dictionary as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main() -> None:
    """Pull selected EODHD fundamentals sections for one ticker."""
    parser = argparse.ArgumentParser(
        description="Pull filtered EODHD fundamentals sections for one ticker."
    )
    parser.add_argument(
        "--ticker",
        default="AAPL.US",
        help="Ticker in EODHD format, e.g. AAPL.US",
    )
    args = parser.parse_args()

    client = EODHDClient()

    print(f"Starting EODHD pull for {args.ticker}")

    for section in SECTIONS:
        print(f"Pulling {args.ticker} {section}...")

        try:
            data = client.get_fundamentals_section(args.ticker, section)
        except Exception as exc:
            print(f"ERROR pulling {args.ticker} {section}: {exc}")
            continue

        output_path = Path("data/raw") / f"{args.ticker}_{section}.json"
        save_json(data, output_path)

        print(f"Saved {output_path}")

    print("Done.")


if __name__ == "__main__":
    main()