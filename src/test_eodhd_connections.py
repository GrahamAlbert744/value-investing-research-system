import json
from pathlib import Path

from src.eodhd_client import EODHDClient, payload_hash


def main():
    client = EODHDClient()

    ticker = "AAPL.US"
    section = "General"

    result = client.get_fundamentals_section(ticker, section)

    output_dir = Path("outputs/raw_samples")
    output_dir.mkdir(parents=True, exist_ok=True)

    h = payload_hash(result)
    output_file = output_dir / f"{ticker}_{section}_{h[:12]}.json"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("Connection test complete.")
    print(f"Ticker: {ticker}")
    print(f"Section: {section}")
    print(f"Status code: {result['metadata']['status_code']}")
    print(f"Saved raw response to: {output_file}")

    data = result["data"]

    if isinstance(data, dict):
        print("Top-level fields:")
        for key in list(data.keys())[:25]:
            print(f"  - {key}")
    else:
        print(f"Unexpected response type: {type(data)}")


if __name__ == "__main__":
    main()
