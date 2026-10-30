from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.forecast import category_scores, forecast, score_breakdown, walk_forward_brier
from src.indicators import calculate_indicators, forward_outcomes
from src.pipeline import run_daily_update
from src.storage import load_forecasts, load_market_data

st.set_page_config(page_title="SPY Market Intelligence", page_icon="📈", layout="wide")
st.title("SPY Market Intelligence")
st.caption("Research MVP · daily market context, historical outcomes, and explicit data limitations")

with st.sidebar:
    st.subheader("Data")
    if st.button("Refresh market data", type="primary"):
        try:
            with st.spinner("Retrieving market data and updating the local database…"):
                run_daily_update()
            st.success("Update completed")
        except Exception as error:
            st.error(f"Update failed: {error}")
    st.caption("Data is sourced from Yahoo Finance through yfinance. It is best-effort and not a licensed production feed.")

prices, metadata = load_market_data()
if prices.empty or "SPY" not in prices:
    st.warning("No local market history yet. Select **Refresh market data** to fetch it.")
    st.stop()

spy_ohlc = pd.DataFrame(index=prices.index)
for field in ("Open", "High", "Low", "Close", "Volume"):
    column = f"SPY_{field}"
    if column in prices:
        spy_ohlc[field] = prices[column]
indicators = calculate_indicators(prices, spy_ohlc)
latest = indicators.iloc[-1]
forecast_result = forecast(indicators)
last_date = indicators.index[-1]

if last_date.date() < pd.Timestamp.now(tz="America/New_York").date():
    st.warning(f"Latest stored session is {last_date.date()}; data may be stale. Refresh to check for a newer session.")

left, middle, right = st.columns(3)
left.metric("SPY close", f"${latest['spy_close']:,.2f}", f"{latest['return_5d']:.2%} · 5 sessions" if pd.notna(latest["return_5d"]) else None)
middle.metric("Session", last_date.strftime("%Y-%m-%d"))
right.metric("Source", "Yahoo Finance · best effort")

if forecast_result["status"] != "available":
    st.info(f"Insufficient evidence for a historical forecast ({forecast_result.get('observations', 0)} usable observations).")
else:
    st.subheader("20-session historical reference")
    cols = st.columns(5)
    cols[0].metric(
        "Positive-return frequency",
        f"{forecast_result['positive_probability']:.1%}",
        help="Share of historical 20-session analogues that finished with a positive SPY return. Analogues match the sign of the current trailing 20-session return. Windows overlap, so observations are not independent; this is not a calibrated probability.",
    )
    cols[1].metric(
        "Median return",
        f"{forecast_result['median_return']:.2%}",
        help="Median SPY close-to-close total return over the following 20 sessions in the historical analogue sample. Half of those observations were higher and half lower.",
    )
    cols[2].metric(
        "10th–90th percentile",
        f"{forecast_result['p10_return']:.2%} to {forecast_result['p90_return']:.2%}",
        help="The 10th and 90th percentiles of historical forward 20-session SPY returns in the analogue sample. This is a historical range, not a calibrated prediction interval.",
    )
    cols[3].metric(
        "Decline ≥5% frequency",
        f"{forecast_result['decline_5pct_probability']:.1%}",
        help="Share of historical analogues where SPY closed at least 5% below the forecast-day close at any point in the next 20 sessions. It can occur even if SPY later recovers; this is not a calibrated probability.",
    )
    cols[4].metric(
        "Descriptive score",
        f"{forecast_result['score']:.0f}/100",
        help="Weighted heuristic composite of momentum, the RSP/SPY breadth proxy, credit, volatility, Treasury curve, and sector placeholder. It is a score, not a probability or confidence measure. See the decision breakdown below.",
    )
    st.write(f"**Heuristic label:** {forecast_result['regime']} · **Decision layer:** {forecast_result['decision']}")
    st.caption(f"{forecast_result['observations']:,} historical analogues. {forecast_result['method']}. Confidence: {forecast_result['confidence']}. The 20-session windows overlap; these frequencies are not validated probabilities or investment advice.")
    st.subheader("How the label and decision were reached")
    st.write(f"**{forecast_result['regime']} label:** {forecast_result['regime_reason']}")
    st.write(f"**{forecast_result['decision']}:** {forecast_result['decision_reason']}")
    st.caption(f"Decision inputs: {forecast_result['decision_inputs']}")
    breakdown = pd.DataFrame(score_breakdown(latest))
    breakdown["Weight (%)"] = breakdown.pop("Weight") * 100
    st.dataframe(
        breakdown[["Category", "Input", "Category score", "Weight (%)", "Composite contribution"]],
        hide_index=True,
        width="stretch",
        column_config={
            "Category score": st.column_config.NumberColumn(format="%+.1f"),
            "Weight (%)": st.column_config.NumberColumn(format="%.0f"),
            "Composite contribution": st.column_config.NumberColumn(format="%+.2f"),
        },
    )
    with st.expander("Scoring formulas and thresholds"):
        st.dataframe(breakdown[["Category", "Scoring rule"]], hide_index=True, width="stretch")
        st.markdown("Composite score = sum(category score × category weight) ÷ sum(available weights). Scores are clipped to [-100, +100]. Regime: Bullish ≥ +20, Neutral between -20 and +20, Bearish ≤ -20. Decision: BUY BIAS ≥ +35, REDUCE RISK ≤ -35, otherwise HOLD.")

period = st.selectbox("Chart history", ["3 months", "6 months", "1 year", "5 years", "Maximum"], index=2)
days = {"3 months": 63, "6 months": 126, "1 year": 252, "5 years": 1260, "Maximum": len(indicators)}[period]
view = indicators.tail(days)
price_chart = go.Figure()
price_chart.add_trace(go.Scatter(x=view.index, y=view["spy_close"], name="SPY adjusted close", line={"color": "#2563eb", "width": 2}))
for window in (20, 50, 200):
    price_chart.add_trace(go.Scatter(x=view.index, y=view[f"sma_{window}"], name=f"SMA {window}", line={"width": 1}))
price_chart.update_layout(height=460, hovermode="x unified", yaxis_title="USD", margin={"l": 10, "r": 10, "t": 20, "b": 10})
st.plotly_chart(price_chart, width="stretch")

st.subheader("Market indicators")
rows = {
    "20-session return": latest.get("return_20d"),
    "60-session return": latest.get("return_60d"),
    "RSI (14)": latest.get("rsi_14"),
    "Annualized realized volatility (20d)": latest.get("realized_vol_20d"),
    "ATR / price": latest.get("atr_pct"),
    "VIX": latest.get("vix"),
    "LQD / IEF 20-session relative return": latest.get("credit_return_20d"),
    "RSP / SPY 20-session relative return": latest.get("rsp_spy_return_20d"),
    "10y–3m curve (percentage points)": latest.get("curve_10y_3m_pct"),
}
st.dataframe(pd.DataFrame([{"Indicator": name, "Latest value": value} for name, value in rows.items()]), hide_index=True, width="stretch")

st.subheader("Indicator group scores")
scores = category_scores(latest)
score_frame = pd.DataFrame({"Category": list(scores), "Score (-100 to +100)": list(scores.values())})
st.bar_chart(score_frame.set_index("Category"))
st.caption("Breadth uses RSP/SPY as a proxy; constituent-level breadth and sector rotation are not included in this MVP. Macro series use Yahoo Finance yield indices where available.")

st.subheader("Historical forecast record")
history = load_forecasts()
if not history.empty:
    outcomes = forward_outcomes(indicators)
    outcomes.index = outcomes.index.strftime("%Y-%m-%d")
    if "median_return" in history:
        history["actual_20_session_return"] = history["date"].map(outcomes["forward_return"])
        history["forecast_error"] = history["actual_20_session_return"] - history["median_return"]
    st.dataframe(history, width="stretch", hide_index=True)
    st.download_button("Download forecast history CSV", history.to_csv(index=False), "forecast_history.csv", "text/csv")
else:
    st.info("No stored forecasts yet. Run an update to save the first forecast.")

st.subheader("Walk-forward baseline check")
backtest = walk_forward_brier(indicators)
st.json(backtest)
st.caption("This minimal check evaluates an expanding unconditional base rate sampled every 20 sessions. It is not a strategy backtest and does not establish predictive skill.")

with st.expander("System health and source coverage"):
    st.json(metadata)
    st.write({"Local database": "SQLite", "Forecast model version": "mvp-0.1", "Latest stored session": str(last_date.date()), "History rows": len(prices)})
    st.write("Data quality status: Yahoo Finance availability, adjustments, timestamps, and licensing are not independently guaranteed. Verify data before relying on any displayed value.")
