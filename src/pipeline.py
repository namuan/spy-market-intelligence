from __future__ import annotations

from datetime import datetime, timezone
import json

from src.data import fetch_market_data
from src.forecast import forecast, walk_forward_brier
from src.indicators import calculate_indicators
from src.storage import connect, save_forecast, save_market_data


def run_daily_update() -> dict:
    started = datetime.now(timezone.utc).isoformat()
    try:
        close, ohlc, metadata = fetch_market_data()
        save_market_data(close, metadata, ohlc)
        indicators = calculate_indicators(close, ohlc)
        result = forecast(indicators)
        result["backtest"] = walk_forward_brier(indicators)
        result["source"] = metadata["source"]
        result["latest_observation"] = metadata["latest_observation"]
        result["missing_series"] = metadata["missing_series"]
        save_forecast(metadata["latest_observation"], float(indicators["spy_close"].iloc[-1]), result)
        with connect() as connection:
            connection.execute(
                "INSERT INTO pipeline_runs(started_at, status, details) VALUES (?, ?, ?)",
                (started, "success", json.dumps({"latest_observation": metadata["latest_observation"]})),
            )
        return result
    except Exception as error:
        with connect() as connection:
            connection.execute(
                "INSERT INTO pipeline_runs(started_at, status, details) VALUES (?, ?, ?)",
                (started, "failed", json.dumps({"error": str(error)})),
            )
        raise


if __name__ == "__main__":
    print(json.dumps(run_daily_update(), indent=2))
