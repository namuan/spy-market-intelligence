from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_indicators(close: pd.DataFrame, spy_ohlc: pd.DataFrame) -> pd.DataFrame:
    if "SPY" not in close:
        raise ValueError("SPY close prices are required")
    result = pd.DataFrame(index=close.index)
    price = close["SPY"].astype(float)
    result["spy_close"] = price
    for window in (20, 50, 100, 200):
        result[f"sma_{window}"] = price.rolling(window, min_periods=window).mean()
    result["ema_20"] = price.ewm(span=20, adjust=False).mean()
    result["ema_50"] = price.ewm(span=50, adjust=False).mean()
    delta = price.diff()
    average_gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    average_loss = -delta.clip(upper=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    result["rsi_14"] = 100 - 100 / (1 + relative_strength)
    result.loc[average_loss.eq(0) & average_gain.gt(0), "rsi_14"] = 100
    fast = price.ewm(span=12, adjust=False).mean()
    slow = price.ewm(span=26, adjust=False).mean()
    result["macd"] = fast - slow
    result["macd_signal"] = result["macd"].ewm(span=9, adjust=False).mean()
    result["return_5d"] = price.pct_change(5)
    result["return_20d"] = price.pct_change(20)
    result["return_60d"] = price.pct_change(60)
    result["realized_vol_20d"] = price.pct_change().rolling(20).std() * np.sqrt(252)
    if "High" in spy_ohlc and "Low" in spy_ohlc:
        high = spy_ohlc["High"].reindex(result.index).astype(float)
        low = spy_ohlc["Low"].reindex(result.index).astype(float)
        previous = price.shift(1)
        true_range = pd.concat(
            [(high - low), (high - previous).abs(), (low - previous).abs()], axis=1
        ).max(axis=1)
        result["atr_14"] = true_range.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        result["atr_pct"] = result["atr_14"] / price
    if "^VIX" in close:
        vix = close["^VIX"].reindex(result.index)
        result["vix"] = vix
        result["vix_change_5d"] = vix.pct_change(5)
        result["vix_percentile_5y"] = vix.rolling(1260, min_periods=252).rank(pct=True)
    if "LQD" in close and "IEF" in close:
        credit = close["LQD"] / close["IEF"]
        result["credit_ratio"] = credit
        result["credit_ratio_sma_200"] = credit.rolling(200, min_periods=200).mean()
        result["credit_return_20d"] = credit.pct_change(20)
    if "RSP" in close:
        relative = close["RSP"] / price
        result["rsp_spy"] = relative
        result["rsp_spy_return_20d"] = relative.pct_change(20)
    if "^TNX" in close:
        result["treasury_10y_pct"] = close["^TNX"] / 10
        result["treasury_10y_change_20d"] = close["^TNX"].diff(20) / 10
    if "^IRX" in close:
        result["treasury_3m_pct"] = close["^IRX"] / 10
        result["curve_10y_3m_pct"] = result.get("treasury_10y_pct") - result["treasury_3m_pct"]
    result["trend_state"] = np.where(result["return_20d"] >= 0, "positive", "negative")
    return result


def forward_outcomes(indicators: pd.DataFrame, horizon: int = 20) -> pd.DataFrame:
    price = indicators["spy_close"]
    future_return = price.shift(-horizon) / price - 1
    future_path = pd.concat([price.shift(-step) / price - 1 for step in range(1, horizon + 1)], axis=1)
    return pd.DataFrame(
        {
            "forward_return": future_return,
            "max_adverse_excursion": future_path.min(axis=1),
            "max_favourable_excursion": future_path.max(axis=1),
            "decline_3pct": future_path.min(axis=1) <= -0.03,
            "decline_5pct": future_path.min(axis=1) <= -0.05,
        },
        index=indicators.index,
    )
