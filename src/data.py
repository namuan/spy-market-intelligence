from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

TICKERS = ["SPY", "^VIX", "LQD", "IEF", "RSP", "^TNX", "^IRX"]


def fetch_market_data(period: str = "max") -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    downloaded = yf.download(
        TICKERS,
        period=period,
        auto_adjust=True,
        group_by="ticker",
        progress=False,
        threads=True,
    )
    if downloaded.empty:
        raise RuntimeError("The market-data provider returned no observations")
    pieces = {}
    for ticker in TICKERS:
        try:
            frame = downloaded[ticker].copy()
        except (KeyError, TypeError):
            continue
        if "Close" in frame:
            pieces[ticker] = frame
    if "SPY" not in pieces:
        raise RuntimeError("SPY data is unavailable")
    close = pd.DataFrame({ticker: frame["Close"] for ticker, frame in pieces.items()})
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    close = close[~close.index.duplicated(keep="last")].sort_index()
    spy = pieces["SPY"].copy()
    spy.index = pd.to_datetime(spy.index).tz_localize(None).normalize()
    spy = spy[~spy.index.duplicated(keep="last")].sort_index()
    metadata = {
        "source": "Yahoo Finance via yfinance; best-effort, not a licensed production feed",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "available_series": sorted(pieces),
        "missing_series": sorted(set(TICKERS) - set(pieces)),
        "latest_observation": close.index.max().date().isoformat(),
    }
    return close, spy, metadata
