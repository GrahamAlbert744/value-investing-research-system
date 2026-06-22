# Value Investing Research System

This project is a step-by-step data science project for building a value-investing research system using EODHD data, Python, Jupyter Lab, and ChatGPT.

## Goals

- Pull company fundamentals, prices, valuation ratios, dividends, earnings, news, and metadata from EODHD.
- Build a clean local database of company data.
- Track data-quality issues.
- Score companies using a value-investing model.
- Produce a top-50 research queue.
- Generate evidence-based research-note templates.
- Avoid buy/sell recommendations.

## Current Phase

Phase 0: Project setup.

## Planned Phases

1. Single-ticker proof of concept
2. U.S. large-cap sample
3. Global developed-market sample
4. Top-50 ranked screener
5. AI research-note generator
6. Streamlit dashboard
7. Scheduled weekly refresh
8. Scoring and database audit loops

## Tools

- Python
- Jupyter Lab
- GitHub
- EODHD API
- ChatGPT
- EODHD connector in ChatGPT
- pandas
- pytest
- Streamlit, later

## Important Design Principles

- Preserve raw data.
- Normalize data separately.
- Track data quality.
- Separate facts from assumptions.
- Never hallucinate missing fields.
- Never issue buy/sell recommendations.
