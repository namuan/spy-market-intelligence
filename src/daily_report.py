from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from src.forecast import score_breakdown
from src.indicators import calculate_indicators
from src.pipeline import run_daily_update
from src.storage import load_market_data


def _pct(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:.2%}"


def _number(value: float | None, digits: int = 2) -> str:
    return "Unavailable" if value is None else f"{value:,.{digits}f}"


def _card(title: str, value: str, detail: str) -> str:
    return (
        '<section class="card"><div class="label">'
        + html.escape(title)
        + '</div><div class="value">'
        + html.escape(value)
        + '</div><div class="detail">'
        + html.escape(detail)
        + "</div></section>"
    )


def render_daily_report(report_date: str, forecast_result: dict, latest: pd.Series, source: str) -> str:
    available = forecast_result.get("status") == "available"
    score = forecast_result.get("score") if available else None
    score_label = _number(score, 1) + "/100" if score is not None else "Insufficient evidence"
    decision = forecast_result.get("decision", "Insufficient evidence")
    regime = forecast_result.get("regime", "Insufficient evidence")
    cards = [
        _card("SPY adjusted close", f"${latest['spy_close']:,.2f}", f"Session ending {report_date}"),
        _card("Market regime", regime, forecast_result.get("regime_reason", "Not available")),
        _card("Heuristic decision", decision, forecast_result.get("decision_reason", "Not available")),
        _card("Composite score", score_label, "Weighted heuristic score, not a probability"),
    ]
    if available:
        cards.extend(
            [
                _card("Positive-return frequency", _pct(forecast_result["positive_probability"]), "Historical 20-session analogues"),
                _card("Median forward return", _pct(forecast_result["median_return"]), "Historical 20-session outcomes"),
                _card(
                    "10th–90th percentile",
                    f"{_pct(forecast_result['p10_return'])} to {_pct(forecast_result['p90_return'])}",
                    "Historical return range, not a calibrated interval",
                ),
                _card("Decline ≥5% frequency", _pct(forecast_result["decline_5pct_probability"]), "Intraperiod decline from forecast-day close"),
            ]
        )
    card_markup = "\n".join(cards)
    if available:
        score_rows = []
        for item in forecast_result["score_breakdown"]:
            score_rows.append(
                "<tr><td>"
                + html.escape(item["Category"])
                + "</td><td>"
                + html.escape(item["Input"])
                + f"</td><td>{item['Category score']:+.1f}</td><td>{item['Weight']:.0%}</td><td>{item['Composite contribution']:+.2f}</td><td>"
                + html.escape(item["Scoring rule"])
                + "</td></tr>"
            )
        score_table = (
            "<h2>Decision breakdown</h2><p>"
            + html.escape(forecast_result["decision_reason"])
            + "</p><p>"
            + html.escape(forecast_result["decision_inputs"])
            + '</p><div class="table-wrap"><table><thead><tr><th>Category</th><th>Current input</th><th>Score</th><th>Weight</th><th>Contribution</th><th>Scoring rule</th></tr></thead><tbody>'
            + "".join(score_rows)
            + "</tbody></table></div>"
        )
        historical_detail = (
            f"<p>The historical reference uses {forecast_result['observations']:,} matured observations selected by the sign of the current trailing 20-session SPY return. Forward 20-session windows overlap, so observations are not independent. These frequencies are descriptive historical rates, not calibrated probabilities or guarantees.</p>"
        )
    else:
        score_table = "<h2>Decision breakdown</h2><p>Insufficient historical evidence to produce a score or decision.</p>"
        historical_detail = "<p>Insufficient matured history for a historical 20-session reference.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Daily SPY market intelligence report for {html.escape(report_date)}">
<title>SPY Daily Report — {html.escape(report_date)}</title>
<style>
:root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #182230; background: #f5f7fb; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; }}
main {{ width: min(1120px, calc(100% - 36px)); margin: 44px auto 80px; }}
header {{ margin-bottom: 28px; }}
a {{ color: #1d4ed8; }}
.eyebrow {{ color: #64748b; font-size: .82rem; letter-spacing: .08em; text-transform: uppercase; }}
h1 {{ margin: 8px 0; font-size: clamp(2rem, 5vw, 3.2rem); letter-spacing: -.04em; }}
.subtitle {{ color: #526174; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin: 24px 0 38px; }}
.card {{ border: 1px solid #e2e8f0; border-radius: 14px; background: white; padding: 20px; min-height: 132px; }}
.label {{ color: #64748b; font-size: .88rem; }}
.value {{ margin: 12px 0; font-size: 1.75rem; font-weight: 700; letter-spacing: -.03em; }}
.detail {{ color: #64748b; font-size: .86rem; line-height: 1.5; }}
section.content {{ border-top: 1px solid #dbe2ea; padding-top: 18px; margin-top: 30px; }}
h2 {{ margin-top: 0; }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; background: white; font-size: .9rem; }}
th, td {{ padding: 11px 12px; border: 1px solid #e2e8f0; text-align: left; vertical-align: top; }}
th {{ background: #eef2f7; white-space: nowrap; }}
.notice {{ background: #fff8e6; border: 1px solid #f3d58a; border-radius: 12px; padding: 16px 18px; color: #684c0d; line-height: 1.55; }}
footer {{ color: #64748b; margin-top: 40px; font-size: .86rem; line-height: 1.6; }}
@media (max-width: 600px) {{ main {{ width: min(100% - 24px, 1120px); margin-top: 24px; }} .card {{ min-height: 0; }} }}
</style>
</head>
<body>
<main>
<header><a href="../index.html">← All daily reports</a><div class="eyebrow">SPY Market Intelligence · Daily report</div><h1>{html.escape(report_date)}</h1><p class="subtitle">Latest market session · Source: {html.escape(source)}</p></header>
<div class="grid">{card_markup}</div>
<section class="content"><h2>Historical 20-session reference</h2>{historical_detail}</section>
<section class="content">{score_table}</section>
<section class="content"><h2>Data and model limitations</h2><div class="notice">For educational and informational purposes only; not investment advice or a recommendation to buy or sell securities. Market data can be delayed, revised, incomplete, or inaccurate. Scores and forecasts are heuristic and unvalidated. Historical results do not guarantee future performance. The historical observations overlap and should not be interpreted as statistically independent.</div></section>
<footer><p>Data: Yahoo Finance through yfinance; best-effort and not a licensed production feed. Verify provider terms before redistribution.</p><p>Published automatically by the SPY Market Intelligence GitHub Actions workflow.</p></footer>
</main>
</body>
</html>
"""


def render_index(report_files: list[Path]) -> str:
    dates = sorted((path.stem for path in report_files), reverse=True)
    if dates:
        latest = dates[0]
        links = "".join(
            f'<li><a href="reports/{html.escape(date)}.html">{html.escape(date)}</a>'
            + (" <strong>Latest</strong>" if date == latest else "")
            + "</li>"
            for date in dates
        )
        summary = f'<p>Latest report: <a href="reports/{html.escape(latest)}.html">{html.escape(latest)}</a></p>'
    else:
        links = "<li>No daily reports have been published yet.</li>"
        summary = "<p>The first report will appear after the next successful scheduled run.</p>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="Daily SPY market intelligence reports"><title>SPY Market Intelligence Reports</title>
<style>:root {{ font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #182230; background: #f5f7fb; }} body {{ margin: 0; }} main {{ width: min(840px, calc(100% - 36px)); margin: 64px auto; }} h1 {{ letter-spacing: -.04em; }} .panel {{ background: white; border: 1px solid #e2e8f0; border-radius: 14px; padding: 24px; }} a {{ color: #1d4ed8; }} li {{ padding: 8px 0; }} .note {{ color: #64748b; line-height: 1.6; }}</style></head>
<body><main><p class="note">SPY Market Intelligence · Automated daily archive</p><h1>Daily market reports</h1><section class="panel">{summary}<ul>{links}</ul></section><p class="note">Reports contain experimental, unvalidated analysis for informational purposes only. They are not investment advice. Data may be delayed or revised; see each report for methodology and limitations.</p></main></body></html>"""


def publish_report(site_dir: Path = Path("site")) -> Path:
    forecast_result = run_daily_update()
    prices, metadata = load_market_data()
    ohlc = pd.DataFrame(index=prices.index)
    for field in ("Open", "High", "Low", "Close", "Volume"):
        column = f"SPY_{field}"
        if column in prices:
            ohlc[field] = prices[column]
    indicators = calculate_indicators(prices, ohlc)
    report_date = metadata["latest_observation"]
    report_dir = site_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{report_date}.html"
    report_path.write_text(
        render_daily_report(report_date, forecast_result, indicators.iloc[-1], metadata["source"]),
        encoding="utf-8",
    )
    index_path = site_dir / "index.html"
    index_path.write_text(render_index(list(report_dir.glob("????-??-??.html"))), encoding="utf-8")
    return report_path


if __name__ == "__main__":
    print(publish_report())
