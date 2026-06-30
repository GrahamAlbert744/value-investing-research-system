\# C1 Endpoint Access Decision



Date: 2026-06-30



\## Local endpoint audit result



Available with current personal EODHD token:

\- /api/user

\- /api/eod/AAPL.US

\- /api/div/AAPL.US

\- /api/splits/AAPL.US

\- /api/news

\- /api/exchanges-list/

\- /api/exchange-symbol-list/US



Available with demo fundamentals token:

\- /api/fundamentals/AAPL.US

\- /api/v1.1/fundamentals/AAPL.US



Not available with current personal EODHD token:

\- /api/fundamentals/AAPL.US

\- /api/v1.1/fundamentals/AAPL.US

\- /api/calendar/earnings



Skipped:

\- /api/eod-bulk-last-day/US



\## Decision



Use `/api/v1.1/fundamentals/{TICKER}` as the default single-ticker fundamentals endpoint for new project code.



Keep `/api/fundamentals/{TICKER}` only in endpoint audit logic for backward-compatibility testing.



Continue using:

\- EODHD\_API\_TOKEN for EOD prices, dividends, splits, news, exchanges, and exchange-symbol-list

\- EODHD\_FUNDAMENTALS\_TOKEN=demo for AAPL.US fundamentals development



Do not build production multi-ticker fundamentals workflow until personal token has Fundamentals access.



Do not build earnings-calendar dependency yet because current personal token does not have access.



Do not commit `.env` or raw JSON samples.

Do not commit full or partial API tokens.

