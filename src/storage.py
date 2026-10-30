from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/market_intelligence.sqlite3")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS market_data (date TEXT PRIMARY KEY, payload TEXT NOT NULL, metadata TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS forecasts (date TEXT PRIMARY KEY, spy_close REAL, payload TEXT NOT NULL, model_version TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS pipeline_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, status TEXT NOT NULL, details TEXT NOT NULL)"
    )
    return connection


def save_market_data(close: pd.DataFrame, metadata: dict, ohlc: pd.DataFrame | None = None, path: Path = DB_PATH) -> None:
    with connect(path) as connection:
        for date, row in close.iterrows():
            payload = {str(key): float(value) for key, value in row.dropna().to_dict().items()}
            if ohlc is not None and date in ohlc.index:
                payload.update({f"SPY_{key}": float(value) for key, value in ohlc.loc[date].dropna().to_dict().items()})
            connection.execute(
                "INSERT INTO market_data(date, payload, metadata) VALUES (?, ?, ?) ON CONFLICT(date) DO UPDATE SET payload=excluded.payload, metadata=excluded.metadata",
                (date.date().isoformat(), json.dumps(payload), json.dumps(metadata)),
            )


def load_market_data(path: Path = DB_PATH) -> tuple[pd.DataFrame, dict]:
    with connect(path) as connection:
        rows = connection.execute("SELECT date, payload, metadata FROM market_data ORDER BY date").fetchall()
    if not rows:
        return pd.DataFrame(), {}
    records = {pd.Timestamp(date): json.loads(payload) for date, payload, _ in rows}
    latest_metadata = json.loads(rows[-1][2])
    frame = pd.DataFrame.from_dict(records, orient="index").sort_index()
    return frame, latest_metadata


def save_forecast(date: str, spy_close: float, payload: dict, path: Path = DB_PATH) -> None:
    serializable = json.dumps(payload, allow_nan=False)
    with connect(path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO forecasts(date, spy_close, payload, model_version) VALUES (?, ?, ?, ?)",
            (date, spy_close, serializable, "mvp-0.1"),
        )


def load_forecasts(path: Path = DB_PATH) -> pd.DataFrame:
    with connect(path) as connection:
        rows = connection.execute(
            "SELECT date, spy_close, payload, model_version FROM forecasts ORDER BY date DESC"
        ).fetchall()
    output = []
    for date, spy_close, payload, model_version in rows:
        output.append({"date": date, "spy_close": spy_close, "model_version": model_version} | json.loads(payload))
    return pd.DataFrame(output)
