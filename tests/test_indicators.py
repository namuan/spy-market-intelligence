import numpy as np
import pandas as pd
from pathlib import Path

from src.daily_report import render_daily_report, render_index
from src.forecast import composite_score, forecast, score_breakdown
from src.indicators import calculate_indicators, forward_outcomes
from src.storage import load_market_data, save_market_data


def sample_data(size=400):
    dates = pd.bdate_range("2020-01-01", periods=size)
    price = pd.Series(np.linspace(100, 150, size), index=dates)
    close = pd.DataFrame(
        {
            "SPY": price,
            "^VIX": 20.0,
            "LQD": price * 0.8,
            "IEF": price * 0.7,
            "RSP": price * 0.99,
            "^TNX": 40.0,
            "^IRX": 20.0,
        },
        index=dates,
    )
    ohlc = pd.DataFrame({"High": price * 1.01, "Low": price * 0.99, "Volume": np.arange(size, dtype=np.int64)}, index=dates)
    return close, ohlc


def test_indicators_and_forward_returns():
    close, ohlc = sample_data()
    result = calculate_indicators(close, ohlc)
    outcomes = forward_outcomes(result, horizon=20)
    assert result["sma_20"].notna().sum() > 0
    assert result["rsi_14"].dropna().between(0, 100).all()
    assert np.isclose(outcomes["forward_return"].iloc[0], close["SPY"].iloc[20] / close["SPY"].iloc[0] - 1)
    assert outcomes["forward_return"].iloc[-1] != outcomes["forward_return"].iloc[-1]


def test_composite_score_is_bounded_and_weighted():
    scores = {"Price and momentum": 100, "Breadth proxy": 100, "Credit conditions": 0, "Volatility": 0, "Treasury curve": 0, "Sector rotation": 0}
    assert np.isclose(composite_score(scores), 50)


def test_report_contains_decision_breakdown_and_escapes_provider_text():
    close, ohlc = sample_data(700)
    indicators = calculate_indicators(close, ohlc)
    result = forecast(indicators)
    report = render_daily_report("2021-11-02", result, indicators.iloc[-1], "Source <provider>", indicators)
    assert "Decision breakdown" in report
    assert "<th>Contribution</th>" in report
    assert "<th>Scoring rule</th>" in report
    assert report.count('class="score-chart-card"') == 6
    assert '"rangeslider"' in report
    assert '"rangeselector"' in report
    assert '"scrollZoom"' in report
    assert report.count('"autorange":true') == 6
    assert '"type":"candlestick"' in report
    assert "weekly OHLC candles of daily category scores" in report
    assert "Price and momentum" in report
    assert "Source &lt;provider&gt;" in report


def test_report_index_links_archived_reports():
    index = render_index([Path("reports/2026-10-30.html"), Path("reports/2026-10-29.html")])
    assert 'href="reports/2026-10-30.html"' in index
    assert "Latest" in index


def test_market_data_storage_serializes_numeric_values(tmp_path):
    close, ohlc = sample_data(3)
    save_market_data(close, {"source": "test"}, ohlc, tmp_path / "test.sqlite3")
    loaded, metadata = load_market_data(tmp_path / "test.sqlite3")
    assert len(loaded) == 3
    assert "SPY_Volume" in loaded
    assert metadata["source"] == "test"


def test_forecast_is_available_after_sufficient_history():
    close, ohlc = sample_data(700)
    result = calculate_indicators(close, ohlc)
    prediction = forecast(result)
    assert prediction["status"] == "available"
    assert 0 <= prediction["positive_probability"] <= 1
    assert prediction["observations"] >= 60
    assert np.isclose(sum(item["Composite contribution"] for item in prediction["score_breakdown"]), prediction["score"])
    assert prediction["decision"] in {"BUY BIAS", "HOLD", "REDUCE RISK"}
    assert "weighted heuristic composite score" in prediction["decision_inputs"]
    assert len(score_breakdown(result.iloc[-1])) == 6
