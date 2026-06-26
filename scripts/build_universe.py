"""
Build outputs/universe_master.csv from data/universe_seed.csv.

This is Phase 7A:
- start with a manually curated seed universe
- normalize ticker/code/exchange fields
- apply basic exclusion rules
- produce universe_master.csv
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.universe import (
    build_universe_master,
    load_seed_universe,
    load_universe_config,
)


def main() -> None:
    seed_path = PROJECT_ROOT / "data" / "universe_seed.csv"
    config_path = PROJECT_ROOT / "config" / "universe_config.yml"
    output_path = PROJECT_ROOT / "outputs" / "universe_master.csv"

    print(f"Loading seed universe: {seed_path}")
    print(f"Loading universe config: {config_path}")

    seed_df = load_seed_universe(seed_path)
    config = load_universe_config(config_path)

    universe_df = build_universe_master(seed_df=seed_df, config=config)
    universe_df.to_csv(output_path, index=False)

    print(f"\nUniverse master saved to: {output_path}")
    print(f"Rows in seed universe: {len(seed_df)}")
    print(f"Rows in universe master: {len(universe_df)}")
    print(f"Included in universe: {int(universe_df['include_in_universe'].sum())}")
    print(f"Excluded from universe: {int((~universe_df['include_in_universe']).sum())}")

    print("\nSectors included:")
    included = universe_df[universe_df["include_in_universe"]]
    print(included["sector"].value_counts().to_string())

    print("\nUniverse tickers:")
    for ticker in included["ticker"].tolist():
        print(f"- {ticker}")


if __name__ == "__main__":
    main()