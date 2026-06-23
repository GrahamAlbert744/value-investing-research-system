# Data Dictionary

This document tracks EODHD fields discovered during project development.

## AAPL.US Initial Field Audit

Source files:

- `data/raw/AAPL.US_General.json`
- `data/raw/AAPL.US_Highlights.json`
- `data/raw/AAPL.US_Valuation.json`
- `data/raw/AAPL.US_SharesStats.json`
- `data/raw/AAPL.US_SplitsDividends.json`

Generated audit:

- `outputs/reports/AAPL.US_field_audit.csv`

## Sections inspected

| Section | Purpose |
|---|---|
| General | Company identity, sector, exchange, country, metadata |
| Highlights | High-level financial and profitability metrics |
| Valuation | Valuation ratios such as trailing P/E, forward P/E, price/sales, price/book |
| SharesStats | Shares outstanding, float, insider/institutional ownership |
| SplitsDividends | Dividend and split metadata |

## Notes

- Raw EODHD payloads are saved locally but not committed to Git.
- Generated audit outputs are saved locally but not committed to Git.
- Field mappings will be created only after inspecting actual EODHD output.