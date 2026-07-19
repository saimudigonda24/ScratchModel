from collections import Counter
from dataclasses import dataclass
from datetime import date

from app.services.database import list_outcome_dashboard_data, list_regime_labels, save_regime_label


@dataclass
class RegimeInput:
    inflation_change: float = 0.0
    growth_change: float = 0.0
    rates_change: float = 0.0
    credit_spread_change: float = 0.0
    equity_drawdown: float = 0.0
    usd_change: float = 0.0
    commodity_change: float = 0.0


def label_regime(metrics: RegimeInput) -> dict:
    labels: list[str] = []
    evidence: dict[str, float] = {
        "inflation_change": metrics.inflation_change,
        "growth_change": metrics.growth_change,
        "rates_change": metrics.rates_change,
        "credit_spread_change": metrics.credit_spread_change,
        "equity_drawdown": metrics.equity_drawdown,
        "usd_change": metrics.usd_change,
        "commodity_change": metrics.commodity_change,
    }
    if metrics.inflation_change > 0.5:
        labels.append("inflation shock")
    if metrics.inflation_change < -0.3:
        labels.append("disinflation")
    if metrics.rates_change < -0.5:
        labels.append("Fed pivot")
    if metrics.growth_change < -0.4:
        labels.append("recession scare")
    if metrics.growth_change > -0.1 and metrics.inflation_change <= 0:
        labels.append("soft landing")
    if metrics.equity_drawdown > -0.05 and metrics.growth_change >= 0:
        labels.append("risk-on")
    if metrics.equity_drawdown <= -0.1:
        labels.append("risk-off")
    if metrics.usd_change > 0.04:
        labels.append("dollar squeeze")
    if abs(metrics.commodity_change) > 0.08:
        labels.append("commodity shock")
    if metrics.credit_spread_change > 0.4:
        labels.append("credit stress")
    if metrics.credit_spread_change > 0.25 and metrics.usd_change > 0.03:
        labels.append("liquidity stress")
    if not labels:
        labels.append("mixed")
    confidence = min(1.0, 0.45 + 0.08 * len(labels))
    return {"labels": labels, "evidence": evidence, "confidence": confidence}


def save_run_regime_label(run_id: str, period_start: str, metrics: RegimeInput, period_end: str | None = None) -> dict:
    result = label_regime(metrics)
    payload = {
        "run_id": run_id,
        "period_start": period_start,
        "period_end": period_end,
        **result,
    }
    save_regime_label(payload)
    return payload


def infer_regime_for_backtest(as_of: date) -> dict:
    year = as_of.year
    if year == 2020:
        metrics = RegimeInput(growth_change=-0.8, equity_drawdown=-0.2, credit_spread_change=0.8, usd_change=0.05)
    elif year == 2021:
        metrics = RegimeInput(inflation_change=0.7, growth_change=0.4, commodity_change=0.12)
    elif year == 2022:
        metrics = RegimeInput(inflation_change=1.0, rates_change=0.9, equity_drawdown=-0.16, usd_change=0.08)
    elif year == 2023:
        metrics = RegimeInput(growth_change=-0.5, credit_spread_change=0.45, equity_drawdown=-0.08)
    elif year == 2024:
        metrics = RegimeInput(inflation_change=-0.4, growth_change=0.1, rates_change=-0.2, equity_drawdown=-0.03)
    else:
        metrics = RegimeInput()
    return label_regime(metrics)


def regime_coverage_summary() -> dict[str, int]:
    labels = list_regime_labels()
    if not labels:
        return {}
    counter: Counter[str] = Counter()
    for row in labels:
        counter.update(row.get("labels", []))
    return dict(counter)


def dashboard_regime_rows() -> list[dict]:
    return list_regime_labels()
