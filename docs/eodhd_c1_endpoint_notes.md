\# EODHD C1 Endpoint Notes



Date captured: 2026-06-30



Purpose:

Use this as a reference for endpoint/version decisions during Correction Phase C1.



Important:

\- Do not paste or store API tokens here.

\- Do not treat this as final truth until compared against outputs/api\_access\_report.csv.

\- Local token audit results override generic endpoint guidance.





According to EODHD’s current docs as checked on \*\*June 30, 2026\*\*: \*\*new integrations should use\*\*:



```text

https://eodhd.com/api/v1.1/fundamentals/{TICKER}

```



not the unversioned `/api/fundamentals/{TICKER}` route. EODHD explicitly says v1.1 is recommended for all new integrations, while the original unversioned endpoint remains available for backward compatibility. The docs do \*\*not\*\* say the old route is deprecated, so mark “deprecated” as \*\*NEEDS\_VERIFICATION\*\* rather than assuming it. (\[EODHD]\[1])



\## Fundamentals route comparison



| Topic                            |                                                                                                    `/api/fundamentals/{TICKER}` |                                                       `/api/v1.1/fundamentals/{TICKER}` |

| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------: | --------------------------------------------------------------------------------------: |

| Recommended for new integrations |                                                                                                                              No |                                                                                 \*\*Yes\*\* |

| Availability                     |                                                                                      Still available for backward compatibility |                                                               Current recommended route |

| Deprecated?                      |                                                         \*\*NEEDS\_VERIFICATION\*\* — docs say backward-compatible, not “deprecated” |                                                            No indication of deprecation |

| Plan-specific?                   | Fundamentals access requires the \*\*Fundamentals package or higher\*\*; the route version itself is not described as plan-specific |        Same package requirement; route version itself is not described as plan-specific |

| Key behavioral change            |                                    Original Earnings Trend could drop Q4 data when quarterly and annual estimates shared a date | Fixes that issue; Earnings Trend is split into Quarterly and Annual with quarter labels |

| Existing parameters              |                                                                                                          Supported historically |                                    Docs say “all existing parameters work the same way” |



EODHD states that to access the Fundamentals API you need the Fundamentals package or higher, and that the Fundamentals API supports only JSON because of the data structure. (\[EODHD]\[1]) Bulk Fundamentals is a separate endpoint/feature and is explicitly tied to the Extended Fundamentals plan, so do not confuse that with single-ticker fundamentals. (\[EODHD]\[2])



\## Does `filter` work identically?



\*\*Best answer: yes for new integrations, with one caveat.\*\* EODHD’s v1.1 documentation says all existing parameters work the same way when moving from `/api/fundamentals/` to `/api/v1.1/fundamentals/`. (\[EODHD]\[1]) Current docs show v1.1 examples for `filter=General::Code`, multiple filters including `General,Earnings`, `filter=Financials::Balance\_Sheet::yearly`, and `filter=Earnings::Trend`. (\[EODHD]\[1])



For the exact sections you named:



| Filter       | Status                                                                                                                                                                                                                                                                         |

| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |

| `General`    | Confirmed in current v1.1 docs                                                                                                                                                                                                                                                 |

| `Highlights` | Supported by legacy/local EODHD reference and live unversioned demo response; v1.1 identical behavior follows from “all existing parameters work the same way,” but exact v1.1 live fetch was not directly verified here — \*\*NEEDS\_VERIFICATION\*\* if you require test evidence |

| `Valuation`  | Same as Highlights — supported in legacy/local reference and live unversioned demo response; exact v1.1 live fetch not directly verified here — \*\*NEEDS\_VERIFICATION\*\*                                                                                                         |

| `Earnings`   | Confirmed in current v1.1 docs; note `Earnings::Trend` changed structure in v1.1                                                                                                                                                                                               |

| `Financials` | Confirmed in current v1.1 docs                                                                                                                                                                                                                                                 |



The local EODHD reference lists `General`, `Highlights`, `Valuation`, `Earnings`, and `Financials` among common-stock top-level fundamentals sections usable with `filter`.  Live checks of the unversioned route returned valid JSON for `filter=Highlights` and `filter=Valuation`, confirming those filters still work on the backward-compatible route. (\[EODHD]\[3])



\## Safest endpoints to use



| Purpose                                    | Safest endpoint                                                                                                                                                                                                       |

| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |

| User/account details                       | `GET https://eodhd.com/api/user?api\_token={API\_TOKEN}\&fmt=json`                                                                                                                                                       |

| Internal user/account/package availability | `GET https://eodhd.com/api/internal-user?api\_token={API\_TOKEN}\&fmt=json` — \*\*NEEDS\_VERIFICATION\*\* against public docs; this is present in the local integration instructions, while public docs emphasize `/api/user` |

| EOD historical prices                      | `GET https://eodhd.com/api/eod/{TICKER}?api\_token={API\_TOKEN}\&fmt=json`                                                                                                                                               |

| Historical dividends                       | `GET https://eodhd.com/api/div/{TICKER}?api\_token={API\_TOKEN}\&fmt=json`                                                                                                                                               |

| Historical splits                          | `GET https://eodhd.com/api/splits/{TICKER}?api\_token={API\_TOKEN}\&fmt=json`                                                                                                                                            |

| Earnings calendar                          | `GET https://eodhd.com/api/calendar/earnings?from={YYYY-MM-DD}\&to={YYYY-MM-DD}\&api\_token={API\_TOKEN}\&fmt=json` or `symbols=...`                                                                                       |

| News                                       | `GET https://eodhd.com/api/news?s={TICKER}\&api\_token={API\_TOKEN}\&fmt=json` or `t={TAG}`                                                                                                                               |

| Exchanges list                             | `GET https://eodhd.com/api/exchanges-list/?api\_token={API\_TOKEN}\&fmt=json`                                                                                                                                            |

| Exchange symbol list                       | `GET https://eodhd.com/api/exchange-symbol-list/{EXCHANGE\_CODE}?api\_token={API\_TOKEN}\&fmt=json`                                                                                                                       |



Official docs confirm `/api/user` for account details. (\[EODHD]\[4]) EOD prices are documented at `/api/eod/{TICKER}` and the free plan has limited EOD history. (\[EODHD]\[5]) Dividends and splits are documented at `/api/div/{TICKER}` and `/api/splits/{TICKER}`. (\[EODHD]\[6]) The earnings calendar endpoint is `/api/calendar/earnings`. (\[EODHD]\[7]) News is `/api/news` and requires either `s` ticker or `t` tag. (\[EODHD]\[8]) Exchanges and symbol lists are documented as `/api/exchanges-list/` and `/api/exchange-symbol-list/{EXCHANGE\_CODE}`. (\[EODHD]\[9])



\## Recommendation



Use \*\*`/api/v1.1/fundamentals/{TICKER}`\*\* for all new single-ticker fundamentals integrations. Keep `/api/fundamentals/{TICKER}` only for existing clients that already depend on it. For `Earnings::Trend`, treat v1.1 as the safer route because it fixes the Q4 collision issue and changes the response structure.



\[1]: https://eodhd.com/financial-apis/stock-etfs-fundamental-data-feeds "The Best Fundamental Data: Stocks, ETFs, Mutual Funds, Indices | Free \& paid plans"

\[2]: https://eodhd.com/financial-apis/bulk-fundamentals-api-via-extended-fundamentals-plan?utm\_source=chatgpt.com "Bulk Fundamentals API (via Extended Fundamentals Plan)"

\[3]: https://eodhd.com/api/fundamentals/AAPL.US?api\_token=demo\&filter=Highlights\&fmt=json "eodhd.com"

\[4]: https://eodhd.com/financial-apis/user-api "User API | EODHD APIs Documentation"

\[5]: https://eodhd.com/financial-apis/api-for-historical-data-and-volumes "End-of-Day Historical Stock Market Data API: The Best Web Service Offering a Free Trial, Providing Real-Time, JSON-Formatted Data Available for Download"

\[6]: https://eodhd.com/financial-apis/api-splits-dividends "Historical Splits and History Dividend Data | Free plan API"

\[7]: https://eodhd.com/financial-apis/calendar-upcoming-earnings-ipos-and-splits "Calendar API: Upcoming Earnings, Trends, IPOs and Splits | EODHD APIs"

\[8]: https://eodhd.com/financial-apis/stock-market-financial-news-api "Financial News Feed and Stock News Sentiment data API | EODHD APIs Documentation"

\[9]: https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours "Financial Exchanges API. Get Stock Market Ticker Lists | Free plan"



