# SPY Market Intelligence MVP

A small, transparent Streamlit application for daily SPY monitoring. The MVP includes SPY price/momentum indicators, VIX, LQD/IEF, RSP/SPY, Treasury yield proxies, a heuristic market score, an expanding historical analogue summary, a basic walk-forward unconditional baseline check, local SQLite persistence, and forecast history.

## Disclaimer

This project is for educational and informational purposes only. It is not investment, financial, legal, or tax advice, and it is not a recommendation, offer, or solicitation to buy or sell any security. The dashboard does not consider any user's objectives, financial situation, or risk tolerance. Consult a qualified financial professional before making investment decisions.

Market data may be incomplete, delayed, revised, or inaccurate. Forecasts, scores, classifications, historical frequencies, and backtests are experimental, heuristic, and unvalidated; they are not guarantees of future results. Investing involves risk, including the possible loss of principal. Independently verify data and calculations before relying on them.

The project code is distributed under the [MIT License](LICENSE). That license does not grant rights to third-party market data or change the data providers' terms of use.

## Dashboard screenshots

Captured from the running dashboard with Yahoo Finance data on 2026-10-30. Displayed market values are historical snapshots and may no longer be current.

**Desktop**

![SPY Market Intelligence dashboard at desktop width](screenshots/dashboard-desktop.png)

**Mobile**

![SPY Market Intelligence dashboard at mobile width](screenshots/dashboard-mobile.png)

## Run locally

```bash
uv sync --extra test
uv run python -m src.pipeline
uv run streamlit run app.py
```

The database is created at `data/market_intelligence.sqlite3`. Click **Refresh market data** in the sidebar to fetch current data and save a forecast. Run a timezone-aware weekday scheduler at 18:30 America/New_York with:

```bash
uv run python -m src.scheduler
```

Keep this process running under a process manager on the machine that owns the SQLite database. The pipeline also runs once on demand:

```bash
uv run python -m src.pipeline
```

## MVP assumptions and limitations

- Yahoo Finance through `yfinance` is the default no-key development source. It is best-effort, may be delayed or revised, and is not a licensed production data feed. Confirm provider terms before redistribution or production use.
- Adjusted daily prices are used for return calculations. Yahoo Finance `^TNX` and `^IRX` are yield-index proxies, not a point-in-time macroeconomic database. The 3-month / 10-year curve is illustrative.
- SQLite is used for a zero-configuration MVP. The production specification calls for PostgreSQL; migrate before multi-user or hosted deployment.
- RSP/SPY is a breadth proxy, not constituent-level breadth. There is no point-in-time constituent membership, sector rotation model, options dataset, macro release calendar, or licensed credit spread series.
- The score and BUY BIAS / HOLD / REDUCE RISK labels are descriptive heuristics, not validated trading recommendations. Missing categories are disclosed in code-level scope; zero-valued categories are neutral placeholders.
- The 20-session historical reference groups prior matured observations by whether trailing 20-session SPY return was positive or negative. It uses overlapping outcomes and is not a validated analogue model; displayed confidence is intentionally low.
- The Brier check evaluates a simple unconditional expanding base rate at 20-session intervals with a horizon purge. It is a baseline diagnostic, not evidence of forecast skill or an investment strategy backtest.
- Current forecasts are saved once per session date and are immutable. The MVP does not yet store constituent-level source observations or provide production-grade retries, authentication, alerting, or monitoring.


## Tests

```bash
uv run pytest
```
