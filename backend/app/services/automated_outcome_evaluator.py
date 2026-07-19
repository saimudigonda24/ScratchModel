import json
from datetime import date, datetime, timedelta

from app.services.database import (
    connect,
    init_db,
    load_daily_prices,
    load_proxy_override,
    save_opportunity_outcome,
)
from app.services.proxy_mapping import map_idea_to_proxy
from app.services.return_calculator import PricePoint, calculate_return_metrics, metrics_dict


def _price_points(rows: list[dict]) -> list[PricePoint]:
    return [PricePoint(row["date"], row.get("adj_close") or row["close"]) for row in rows]


def _months_elapsed(start_date: str, end_date: str) -> float:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    return (end - start).days / 30.4375


class AutomatedOutcomeEvaluator:
    def approved_opportunities(self) -> list[dict]:
        init_db()
        conn = connect()
        try:
            rows = conn.execute(
                """
                SELECT o.run_id, o.name, o.asset_class, o.conviction_score, o.payload_json, o.created_at
                FROM opportunities o
                JOIN macro_reports mr ON mr.run_id = o.run_id
                WHERE mr.training_approved = 1
                ORDER BY o.id DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def evaluate(self, as_of: str | None = None) -> dict:
        evaluation_date = as_of or date.today().isoformat()
        summary = {"evaluated": 0, "skipped": 0, "details": []}
        for row in self.approved_opportunities():
            idea = json.loads(row["payload_json"])
            override = load_proxy_override(row["run_id"], "opportunity", row["name"])
            mapping = map_idea_to_proxy(row["name"], row["asset_class"], override.get("proxy_ticker") if override else None)
            proxy = override.get("proxy_ticker") if override else mapping.proxy_ticker
            benchmark = override.get("benchmark_ticker") if override else mapping.benchmark
            expected_direction = override.get("expected_direction") if override else mapping.expected_direction
            start_date = override.get("start_date") if override else row["created_at"][:10]
            horizon = override.get("target_horizon_months") if override else idea.get("expected_horizon_months", [7, 14])
            minimum_months = int(horizon[0]) if horizon else 7
            if _months_elapsed(start_date, evaluation_date) < minimum_months:
                summary["skipped"] += 1
                summary["details"].append({"idea": row["name"], "reason": "target horizon not elapsed"})
                continue
            price_rows = load_daily_prices(proxy, start_date, evaluation_date)
            benchmark_rows = load_daily_prices(benchmark, start_date, evaluation_date)
            if len(price_rows) < 2 or len(benchmark_rows) < 2:
                summary["skipped"] += 1
                summary["details"].append({"idea": row["name"], "reason": "missing stored prices", "proxy": proxy, "benchmark": benchmark})
                continue
            metrics = metrics_dict(calculate_return_metrics(_price_points(price_rows), _price_points(benchmark_rows), expected_direction))
            quality_score = min(10.0, max(0.0, row["conviction_score"] + (1 if metrics["hit_miss_label"] == "hit" else -1)))
            payload = {
                "run_id": row["run_id"],
                "idea_id": row["name"],
                "asset_class": row["asset_class"],
                "instrument": proxy,
                "proxy_ticker": proxy,
                "thesis_fit": idea.get("thesis_fit", ""),
                "start_date": start_date,
                "target_horizon_months": horizon,
                "benchmark": benchmark,
                "expected_direction": expected_direction,
                "expected_catalyst": idea.get("catalyst", ""),
                "invalidation_trigger": "; ".join(idea.get("invalidating_data", []) or idea.get("triggers", [])),
                "approved_probability": None,
                "conviction_score": row["conviction_score"],
                "realized_return": metrics["total_return"],
                "benchmark_return": metrics["benchmark_return"],
                "max_drawdown": metrics["max_drawdown"],
                "volatility": metrics["volatility"],
                "sharpe_like": metrics["sharpe_like"],
                "hit_miss_label": metrics["hit_miss_label"],
                "outcome_evaluated": True,
                "outcome_quality_score": quality_score,
                "eligible_for_fine_tuning": quality_score >= 6.0 and bool(idea.get("evidence")) and bool(idea.get("risks")),
                "notes": override.get("notes", "") if override else mapping.rationale,
            }
            save_opportunity_outcome(payload)
            summary["evaluated"] += 1
            summary["details"].append({"idea": row["name"], "proxy": proxy, "hit_miss_label": metrics["hit_miss_label"]})
        return summary

