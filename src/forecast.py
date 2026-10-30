from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators import forward_outcomes

FEATURES = ["return_20d", "realized_vol_20d", "vix", "credit_return_20d", "rsp_spy_return_20d"]
SCORE_WEIGHTS = {
    "Price and momentum": 0.25,
    "Breadth proxy": 0.25,
    "Credit conditions": 0.15,
    "Volatility": 0.15,
    "Treasury curve": 0.10,
    "Sector rotation": 0.10,
}
SCORE_FORMULAS = {
    "Price and momentum": "clip(20-session SPY return × 700, -100, +100)",
    "Breadth proxy": "clip(20-session RSP/SPY ratio return × 1,500, -100, +100)",
    "Credit conditions": "clip(20-session LQD/IEF ratio return × 1,500, -100, +100)",
    "Volatility": "clip(30 − spot VIX × 1.5, -100, +100)",
    "Treasury curve": "clip(−(10y − 3m yield, percentage points) × 12, -100, +100)",
    "Sector rotation": "0; neutral placeholder, not implemented",
}


def category_scores(row: pd.Series) -> dict[str, float]:
    momentum = _bounded((row.get("return_20d", 0) or 0) * 700)
    breadth = _bounded((row.get("rsp_spy_return_20d", 0) or 0) * 1500)
    credit = _bounded((row.get("credit_return_20d", 0) or 0) * 1500)
    volatility = _bounded(30 - (row.get("vix", 20) or 20) * 1.5)
    macro = _bounded(-(row.get("curve_10y_3m_pct", 0) or 0) * 12)
    sector = 0.0
    return {
        "Price and momentum": momentum,
        "Breadth proxy": breadth,
        "Credit conditions": credit,
        "Volatility": volatility,
        "Treasury curve": macro,
        "Sector rotation": sector,
    }


def _bounded(value: float) -> float:
    if not np.isfinite(value):
        return 0.0
    return float(np.clip(value, -100, 100))


def composite_score(scores: dict[str, float]) -> float:
    available = {name: score for name, score in scores.items() if name in SCORE_WEIGHTS and np.isfinite(score)}
    if len(available) < 3:
        return float("nan")
    denominator = sum(SCORE_WEIGHTS[name] for name in available)
    return float(sum(SCORE_WEIGHTS[name] * score for name, score in available.items()) / denominator)


def score_breakdown(row: pd.Series) -> list[dict]:
    scores = category_scores(row)
    available_weight = sum(SCORE_WEIGHTS[name] for name, score in scores.items() if np.isfinite(score))
    raw_inputs = {
        "Price and momentum": row.get("return_20d"),
        "Breadth proxy": row.get("rsp_spy_return_20d"),
        "Credit conditions": row.get("credit_return_20d"),
        "Volatility": row.get("vix"),
        "Treasury curve": row.get("curve_10y_3m_pct"),
        "Sector rotation": None,
    }
    input_labels = {
        "Price and momentum": "20-session SPY return",
        "Breadth proxy": "20-session RSP/SPY ratio return",
        "Credit conditions": "20-session LQD/IEF ratio return",
        "Volatility": "Spot VIX level",
        "Treasury curve": "10y−3m curve, percentage points",
        "Sector rotation": "Not implemented",
    }
    details = []
    for name, score in scores.items():
        raw_value = raw_inputs[name]
        input_value = "Neutral placeholder" if raw_value is None else (
            f"{raw_value:.2%}" if name in {"Price and momentum", "Breadth proxy", "Credit conditions"}
            else f"{raw_value:.2f}"
        )
        weight = SCORE_WEIGHTS[name]
        contribution = weight * score / available_weight
        details.append(
            {
                "Category": name,
                "Input": f"{input_labels[name]}: {input_value}",
                "Scoring rule": SCORE_FORMULAS[name],
                "Category score": score,
                "Weight": weight,
                "Composite contribution": contribution,
            }
        )
    return details


def forecast(indicators: pd.DataFrame, horizon: int = 20, min_history: int = 60) -> dict:
    outcomes = forward_outcomes(indicators, horizon)
    current = indicators.iloc[-1]
    target_date = indicators.index[-1]
    valid = outcomes["forward_return"].notna()
    history = indicators.loc[valid].join(outcomes.loc[valid])
    if len(history) < min_history:
        return {"status": "insufficient_evidence", "observations": len(history)}
    asof_history = history.loc[history.index < target_date]
    last_matured_date = indicators.index[max(0, len(indicators) - horizon - 1)]
    matured = asof_history.loc[asof_history.index <= last_matured_date]
    matured = matured.dropna(subset=["forward_return", "return_20d"])
    if len(matured) < min_history:
        return {"status": "insufficient_evidence", "observations": len(matured)}
    conditional = matured.loc[matured["return_20d"].ge(0)]
    if current.get("return_20d", 0) < 0:
        conditional = matured.loc[matured["return_20d"].lt(0)]
    sample = conditional if len(conditional) >= min_history else matured
    returns = sample["forward_return"].dropna()
    scores = category_scores(current)
    score = composite_score(scores)
    regime = "Bullish" if score >= 20 else "Bearish" if score <= -20 else "Neutral"
    decision = "BUY BIAS" if score >= 35 else "REDUCE RISK" if score <= -35 else "HOLD"
    if decision == "BUY BIAS":
        decision_reason = f"The composite score {score:.1f} meets the BUY BIAS threshold of +35."
    elif decision == "REDUCE RISK":
        decision_reason = f"The composite score {score:.1f} meets the REDUCE RISK threshold of -35."
    else:
        decision_reason = f"The composite score {score:.1f} is between the +35 BUY BIAS and -35 REDUCE RISK thresholds, so the rule returns HOLD."
    if regime == "Bullish":
        regime_reason = f"The score {score:.1f} is at or above the +20 bullish boundary."
    elif regime == "Bearish":
        regime_reason = f"The score {score:.1f} is at or below the -20 bearish boundary."
    else:
        regime_reason = f"The score {score:.1f} is between the -20 and +20 neutral boundaries."
    return {
        "status": "available",
        "observations": int(len(sample)),
        "positive_probability": float(returns.gt(0).mean()),
        "negative_probability": float(returns.le(0).mean()),
        "decline_3pct_probability": float(sample["decline_3pct"].mean()),
        "decline_5pct_probability": float(sample["decline_5pct"].mean()),
        "median_return": float(returns.median()),
        "mean_return": float(returns.mean()),
        "p10_return": float(returns.quantile(0.1)),
        "p90_return": float(returns.quantile(0.9)),
        "score": score,
        "category_scores": scores,
        "score_breakdown": score_breakdown(current),
        "regime": regime,
        "regime_reason": regime_reason,
        "decision": decision,
        "decision_reason": decision_reason,
        "decision_inputs": "Only the weighted heuristic composite score; historical return and drawdown frequencies are context and do not alter the decision label.",
        "confidence": "Low; overlapping historical outcomes and unvalidated heuristic",
        "method": "Expanding historical analogue by sign of trailing 20-session SPY return; not a validated predictive model",
    }


def walk_forward_brier(indicators: pd.DataFrame, horizon: int = 20, min_history: int = 252) -> dict:
    outcomes = forward_outcomes(indicators, horizon)
    predictions = []
    actuals = []
    for position in range(min_history + horizon, len(indicators) - horizon, 20):
        date = indicators.index[position]
        training_end = position - horizon
        history = outcomes.iloc[:training_end].dropna(subset=["forward_return"])
        if len(history) < min_history:
            continue
        probability = float(history["forward_return"].gt(0).mean())
        actual = float(outcomes.iloc[position]["forward_return"] > 0)
        predictions.append(probability)
        actuals.append(actual)
    if not predictions:
        return {"forecasts": 0, "brier_score": None}
    return {
        "forecasts": len(predictions),
        "brier_score": float(np.mean((np.asarray(predictions) - np.asarray(actuals)) ** 2)),
        "baseline": "Expanding unconditional positive-return frequency, sampled every 20 sessions; horizon purged",
    }
