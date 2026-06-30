\# EODHD Value Investing Project — Correction Sprint Checklist



Purpose: harden the current MVP after reviewing EODHD connector feedback.



This is not a rebuild. The existing project remains valid, but several areas need stricter validation before scaling beyond the demo/AAPL prototype.



\## C0 — Checklist and checkpoint



\- \[ ] Create this checklist file

\- \[ ] Confirm current Git status

\- \[ ] Confirm no secrets are tracked

\- \[ ] Commit checklist



\## C1 — Endpoint/access audit



Goal: confirm exact EODHD endpoints and token access before further API expansion.



Files:

\- config/eodhd\_endpoint\_config.yml

\- scripts/build\_api\_access\_report.py

\- outputs/api\_access\_report.csv



Checks:

\- \[ ] Test `/api/user`

\- \[ ] Test `/api/eod/AAPL.US`

\- \[ ] Test `/api/fundamentals/AAPL.US`

\- \[ ] Test `/api/v1.1/fundamentals/AAPL.US`

\- \[ ] Test `/api/div/AAPL.US`

\- \[ ] Test `/api/splits/AAPL.US`

\- \[ ] Test `/api/calendar/earnings`

\- \[ ] Test `/api/news`

\- \[ ] Test `/api/exchanges-list`

\- \[ ] Test `/api/exchange-symbol-list/US`

\- \[ ] Save redacted `outputs/api\_access\_report.csv`

\- \[ ] Do not print or commit API token



EODHD prompt:

For EODHD fundamentals in 2026, should new integrations use /api/fundamentals/{TICKER} or /api/v1.1/fundamentals/{TICKER}? Please compare both routes, explain whether either is deprecated or plan-specific, and confirm whether the filter parameter works identically for General, Highlights, Valuation, Earnings, and Financials. Mark uncertain details as NEEDS\_VERIFICATION.



\## C2 — Field mapping fallback-path revision



Goal: allow normalized fields to use multiple possible raw paths.



Files:

\- config/field\_mapping.yml

\- src/normalization.py

\- scripts/create\_initial\_field\_mapping.py

\- tests/test\_normalization.py

\- outputs/normalized\_metrics.csv



Checks:

\- \[ ] Add support for `raw\_paths`

\- \[ ] Preserve backward compatibility with `raw\_path`

\- \[ ] Add identity/staleness/share fields

\- \[ ] Rerun normalization

\- \[ ] Update tests



Fields to add:

\- code

\- primary\_ticker

\- security\_type

\- country\_iso

\- is\_delisted

\- fundamentals\_updated\_at

\- most\_recent\_quarter

\- shares\_outstanding

\- beta

\- isin

\- fiscal\_year\_end

\- ipo\_date



\## C3 — Expanded data-quality rules



Goal: add rules for stale data, delisting, security type, currency, and financial statement coverage.



Files:

\- config/data\_quality\_rules.yml

\- src/data\_quality.py

\- tests/test\_data\_quality.py

\- config/financial\_statement\_quality\_rules.yml

\- src/financial\_statement\_quality.py

\- tests/test\_financial\_statement\_quality.py



Checks:

\- \[ ] Stale fundamentals rule

\- \[ ] Stale price rule

\- \[ ] Delisted security rule

\- \[ ] Non-common-stock rule

\- \[ ] Missing/invalid market cap rule

\- \[ ] Currency mismatch rule

\- \[ ] Missing statements rule

\- \[ ] Negative equity rule

\- \[ ] Suspicious valuation ratio rules



\## C4 — Financial statement metadata upgrade



Goal: preserve better metadata in long-format financial statements.



Files:

\- src/financials.py

\- tests/test\_financials.py

\- outputs/financial\_statement\_lines.csv



Checks:

\- \[ ] Add raw\_value\_type

\- \[ ] Add standard\_period\_type

\- \[ ] Add statement\_currency\_source

\- \[ ] Add quality\_flags

\- \[ ] Preserve source\_path

\- \[ ] Preserve extracted\_at\_utc



\## C5 — Financial statement summary upgrade



Goal: add multi-year metrics before revising scoring.



Files:

\- src/financial\_statement\_summary.py

\- scripts/build\_financial\_statement\_summary.py

\- tests/test\_financial\_statement\_summary.py

\- outputs/financial\_statement\_summary.csv



Checks:

\- \[ ] revenue\_cagr\_3y

\- \[ ] net\_income\_cagr\_3y

\- \[ ] fcf\_cagr\_3y

\- \[ ] positive\_net\_income\_years

\- \[ ] positive\_fcf\_years

\- \[ ] revenue\_volatility

\- \[ ] net\_margin\_volatility

\- \[ ] earnings\_yield

\- \[ ] fcf\_yield



\## C6 — Scoring missing-data revision



Goal: replace neutral missing-metric scoring with coverage/reweighting logic.



Files:

\- config/scoring\_config.yml

\- src/scoring.py

\- src/scoring\_outputs.py

\- tests/test\_scoring.py

\- tests/test\_scoring\_outputs.py

\- outputs/all\_scored\_stocks.csv

\- outputs/scoring\_metric\_details.csv



Checks:

\- \[ ] Add category coverage threshold

\- \[ ] Reweight only if category coverage >= 60%

\- \[ ] Prevent missing data from inflating scores

\- \[ ] Add category confidence

\- \[ ] Add score\_data\_coverage

\- \[ ] Update metric detail output



\## C7 — Price + per-share valuation upgrade



Goal: move from market-cap-based valuation MVP to per-share valuation.



Files:

\- src/eodhd\_client.py

\- scripts/update\_prices.py

\- outputs/latest\_prices.csv

\- config/valuation\_config.yml

\- src/valuation.py

\- tests/test\_valuation.py

\- outputs/valuation\_outputs.csv



Checks:

\- \[ ] Pull latest EOD price

\- \[ ] Use adjusted\_close or close with explicit rule

\- \[ ] Use shares\_outstanding

\- \[ ] Calculate fair value per share low/base/high

\- \[ ] Calculate current-price margin of safety

\- \[ ] Add unreliable valuation gates



\## C8 — Research queue gates/diversification



Goal: apply gates before ranking and add sector/industry caps.



Files:

\- config/research\_queue\_config.yml

\- src/research\_queue.py

\- scripts/create\_research\_queue.py

\- tests/test\_research\_queue.py

\- outputs/research\_queue.csv

\- outputs/top\_50\_research\_queue.csv



Checks:

\- \[ ] Reject critical failures

\- \[ ] Hold missing critical data

\- \[ ] Watchlist low-confidence stocks

\- \[ ] Rank only eligible candidates

\- \[ ] Add sector cap: 20%

\- \[ ] Add industry cap: 10%

\- \[ ] Add deep-value exception warning

\- \[ ] Preserve rejected-stock audit



\## C9 — Full pipeline rerun



Goal: prove the hardened pipeline runs end to end.



Commands:

\- \[ ] python -m pytest -v

\- \[ ] python scripts\\check\_eodhd\_connection.py

\- \[ ] python scripts\\normalize\_latest\_fundamentals.py

\- \[ ] python scripts\\run\_data\_quality\_audit.py

\- \[ ] python scripts\\extract\_financial\_statements.py

\- \[ ] python scripts\\run\_financial\_statement\_quality\_audit.py

\- \[ ] python scripts\\build\_financial\_statement\_summary.py

\- \[ ] python scripts\\build\_scoring\_outputs.py

\- \[ ] python scripts\\run\_valuation.py

\- \[ ] python scripts\\create\_research\_queue.py



Final rule:

Do not commit `.env` or `outputs/raw\_samples/\*.json`.

