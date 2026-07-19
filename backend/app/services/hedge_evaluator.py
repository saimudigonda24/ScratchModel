from app.services.database import save_hedge_outcome
from app.services.return_calculator import PricePoint, hedge_effectiveness, max_drawdown, periodic_returns, realized_volatility, total_return


def detect_stress_windows(
    equity_prices: list[PricePoint],
    threshold: float = -0.1,
    vix_prices: list[PricePoint] | None = None,
    credit_spread_prices: list[PricePoint] | None = None,
    rates_vol_prices: list[PricePoint] | None = None,
    usd_prices: list[PricePoint] | None = None,
    commodity_prices: list[PricePoint] | None = None,
) -> list[dict]:
    windows: list[dict] = []
    peak = equity_prices[0].close if equity_prices else 0.0
    active_start = None
    for point in equity_prices:
        peak = max(peak, point.close)
        drawdown = point.close / peak - 1 if peak else 0.0
        if drawdown <= threshold and active_start is None:
            active_start = point.date
        if active_start and drawdown > threshold / 2:
            windows.append({"start": active_start, "end": point.date, "max_drawdown": drawdown, "source": "equity_drawdown"})
            active_start = None
    if active_start:
        windows.append({"start": active_start, "end": equity_prices[-1].date, "max_drawdown": max_drawdown(equity_prices), "source": "equity_drawdown"})
    windows.extend(_shock_windows(vix_prices or [], "vix_proxy", 0.15))
    windows.extend(_shock_windows(credit_spread_prices or [], "credit_spread_proxy", 0.08))
    windows.extend(_shock_windows(rates_vol_prices or [], "rates_vol_proxy", 0.08))
    windows.extend(_shock_windows(usd_prices or [], "usd_squeeze", 0.04))
    windows.extend(_shock_windows(commodity_prices or [], "commodity_shock", 0.08, absolute=True))
    return _merge_windows(windows)


def _shock_windows(prices: list[PricePoint], source: str, threshold: float, absolute: bool = False) -> list[dict]:
    returns = periodic_returns(prices)
    windows = []
    for index, value in enumerate(returns, start=1):
        trigger = abs(value) >= threshold if absolute else value >= threshold
        if trigger and index < len(prices):
            windows.append({"start": prices[index - 1].date, "end": prices[index].date, "shock_return": value, "source": source})
    return windows


def _merge_windows(windows: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str], dict] = {}
    for window in windows:
        key = (window["start"], window["end"])
        existing = deduped.get(key)
        if existing:
            existing["source"] = f"{existing['source']},{window['source']}"
        else:
            deduped[key] = dict(window)
    return sorted(deduped.values(), key=lambda row: row["start"])


def evaluate_hedge(
    run_id: str,
    hedge: dict,
    hedge_prices: list[PricePoint],
    opportunity_set_prices: list[PricePoint],
    proxy_ticker: str,
    vix_prices: list[PricePoint] | None = None,
    credit_spread_prices: list[PricePoint] | None = None,
    rates_vol_prices: list[PricePoint] | None = None,
    usd_prices: list[PricePoint] | None = None,
    commodity_prices: list[PricePoint] | None = None,
) -> dict:
    hedge_returns = periodic_returns(hedge_prices)
    portfolio_returns = periodic_returns(opportunity_set_prices)
    stress_windows = detect_stress_windows(
        opportunity_set_prices,
        vix_prices=vix_prices,
        credit_spread_prices=credit_spread_prices,
        rates_vol_prices=rates_vol_prices,
        usd_prices=usd_prices,
        commodity_prices=commodity_prices,
    )
    effectiveness = hedge_effectiveness(hedge_returns, portfolio_returns)
    ret = total_return(hedge_prices)
    drag = -ret if ret < 0 else 0.0
    convexity = max(hedge_returns) - min(hedge_returns) if hedge_returns else 0.0
    stress_payoffs = _stress_window_payoffs(stress_windows, hedge_prices)
    stress_hit_rate = sum(1 for payoff in stress_payoffs if payoff > 0) / len(stress_payoffs) if stress_payoffs else 0.0
    stress_payoff = sum(stress_payoffs) / len(stress_payoffs) if stress_payoffs else 0.0
    protected = stress_hit_rate >= 0.5 and stress_payoff > 0
    quality = min(10.0, max(0.0, 5 + effectiveness * 2 + stress_hit_rate * 2 - drag * 10 + convexity + (1 if protected else 0)))
    payload = {
        "run_id": run_id,
        "hedge_id": hedge.get("name", "unknown hedge"),
        "asset_class": hedge.get("asset_class", "cross_asset"),
        "instrument": proxy_ticker,
        "proxy_ticker": proxy_ticker,
        "start_date": hedge_prices[0].date if hedge_prices else "",
        "target_horizon_months": hedge.get("expected_horizon_months", [7, 14]),
        "stress_window": str(stress_windows),
        "hedge_effectiveness": effectiveness,
        "realized_return": ret,
        "max_drawdown": max_drawdown(hedge_prices),
        "volatility": realized_volatility(hedge_prices),
        "outcome_evaluated": True,
        "outcome_quality_score": quality,
        "eligible_for_fine_tuning": quality >= 7.0 and bool(stress_windows),
        "notes": (
            f"Normal-market carry/drag: {drag:.4f}; stress-window payoff: {stress_payoff:.4f}; "
            f"stress-window hit rate: {stress_hit_rate:.2%}; hedge convexity score: {convexity:.4f}; "
            f"timing usefulness: {effectiveness:.2%}; protected opportunity set: {protected}"
        ),
    }
    save_hedge_outcome(payload)
    return payload


def _stress_window_payoffs(windows: list[dict], prices: list[PricePoint]) -> list[float]:
    by_date = {point.date: point.close for point in prices}
    payoffs = []
    for window in windows:
        start = by_date.get(window["start"])
        end = by_date.get(window["end"])
        if start and end:
            payoffs.append(end / start - 1)
    return payoffs
