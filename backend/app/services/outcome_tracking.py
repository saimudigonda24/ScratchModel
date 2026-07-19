from app.services.database import save_opportunity_outcome, save_realized_market_return
from app.services.proxy_mapping import map_idea_to_proxy
from app.services.return_calculator import PricePoint, calculate_return_metrics, metrics_dict


def create_opportunity_outcome_record(
    run_id: str,
    idea: dict,
    prices: list[PricePoint],
    benchmark_prices: list[PricePoint],
    manual_proxy: str | None = None,
) -> dict:
    mapping = map_idea_to_proxy(idea.get("name", ""), idea.get("asset_class", "cross_asset"), manual_proxy)
    metrics = calculate_return_metrics(prices, benchmark_prices, mapping.expected_direction)
    metric_payload = metrics_dict(metrics)
    quality_score = min(10.0, max(0.0, idea.get("conviction_score", 0) + (1 if metric_payload["hit_miss_label"] == "hit" else -1)))
    payload = {
        "run_id": run_id,
        "idea_id": idea.get("name", "unknown"),
        "asset_class": idea.get("asset_class", "cross_asset"),
        "instrument": mapping.proxy_ticker,
        "proxy_ticker": mapping.proxy_ticker,
        "thesis_fit": idea.get("thesis_fit", ""),
        "start_date": prices[0].date if prices else "",
        "target_horizon_months": idea.get("expected_horizon_months", [7, 14]),
        "benchmark": mapping.benchmark,
        "expected_direction": mapping.expected_direction,
        "expected_catalyst": idea.get("catalyst", ""),
        "invalidation_trigger": "; ".join(idea.get("invalidating_data", []) or idea.get("triggers", [])),
        "approved_probability": None,
        "conviction_score": idea.get("conviction_score", 0),
        "realized_return": metric_payload["total_return"],
        "benchmark_return": metric_payload["benchmark_return"],
        "max_drawdown": metric_payload["max_drawdown"],
        "volatility": metric_payload["volatility"],
        "sharpe_like": metric_payload["sharpe_like"],
        "hit_miss_label": metric_payload["hit_miss_label"],
        "outcome_evaluated": True,
        "outcome_quality_score": quality_score,
        "eligible_for_fine_tuning": quality_score >= 6.0 and bool(idea.get("evidence")) and bool(idea.get("risks")),
        "notes": mapping.rationale,
    }
    save_opportunity_outcome(payload)
    if prices:
        save_realized_market_return(
            {
                "ticker": mapping.proxy_ticker,
                "start_date": prices[0].date,
                "end_date": prices[-1].date,
                "total_return": metric_payload["total_return"],
                "max_drawdown": metric_payload["max_drawdown"],
                "volatility": metric_payload["volatility"],
                "sharpe_like": metric_payload["sharpe_like"],
                "source": "outcome_tracking",
            }
        )
    return payload
