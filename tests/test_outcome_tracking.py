import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.database import list_outcome_dashboard_data, outcome_summary, save_forecast_outcome, save_opportunity_outcome
from app.services.forecast_calibration import brier_score, bucket_probability, summarize_calibration
from app.services.proxy_mapping import map_idea_to_proxy
from app.services.return_calculator import (
    PricePoint,
    calculate_return_metrics,
    hedge_effectiveness,
    hit_miss,
    max_drawdown,
    total_return,
)


def test_proxy_mapping_examples():
    assert map_idea_to_proxy("intermediate duration with curve optionality", "fixed_income").proxy_ticker == "IEF"
    assert map_idea_to_proxy("quality equities", "equity").proxy_ticker == "QUAL"
    assert map_idea_to_proxy("gold hedge", "commodity").proxy_ticker == "GLD"
    assert map_idea_to_proxy("selective REITs", "reit").proxy_ticker == "VNQ"
    assert map_idea_to_proxy("crypto beta", "crypto").proxy_ticker == "BTC-USD"
    assert map_idea_to_proxy("anything", "equity", manual_override="QQQ").proxy_ticker == "QQQ"


def test_return_drawdown_and_hit_miss_calculation():
    prices = [
        PricePoint("2024-01-01", 100),
        PricePoint("2024-01-02", 110),
        PricePoint("2024-01-03", 90),
        PricePoint("2024-01-04", 120),
    ]
    benchmark = [
        PricePoint("2024-01-01", 100),
        PricePoint("2024-01-04", 105),
    ]
    metrics = calculate_return_metrics(prices, benchmark, "long")

    assert round(total_return(prices), 4) == 0.2
    assert round(max_drawdown(prices), 4) == round(90 / 110 - 1, 4)
    assert metrics.hit_miss_label == "hit"
    assert hit_miss(0.1, "short") == "miss"
    assert hedge_effectiveness([0.02, -0.01, 0.03], [-0.04, 0.01, -0.02]) == 1.0


def test_brier_score_and_calibration_summary():
    assert round(brier_score(0.7, 1), 4) == 0.09
    assert bucket_probability(0.63) == "60-70%"

    summary = summarize_calibration(
        [
            {"probability": 0.6, "actual_outcome": 1},
            {"probability": 0.6, "actual_outcome": 0},
            {"probability": 0.8, "actual_outcome": 1},
        ]
    )

    assert summary.brier_score > 0
    assert "60-70%" in summary.calibration_buckets


def test_outcome_database_persistence_and_dashboard_formatting():
    payload = {
        "run_id": "test_outcome_run",
        "idea_id": "Quality equities",
        "asset_class": "equity",
        "instrument": "QUAL",
        "proxy_ticker": "QUAL",
        "thesis_fit": "Fits soft landing",
        "start_date": "2024-01-01",
        "target_horizon_months": [7, 14],
        "benchmark": "SPY",
        "expected_direction": "long",
        "expected_catalyst": "Earnings stabilize",
        "invalidation_trigger": "Credit stress",
        "approved_probability": 0.6,
        "conviction_score": 7.0,
        "realized_return": 0.12,
        "benchmark_return": 0.08,
        "max_drawdown": -0.05,
        "volatility": 0.14,
        "sharpe_like": 0.86,
        "hit_miss_label": "hit",
        "outcome_evaluated": True,
        "outcome_quality_score": 8.0,
        "eligible_for_fine_tuning": True,
        "notes": "test row",
    }
    save_opportunity_outcome(payload)
    save_forecast_outcome(
        {
            "run_id": "test_outcome_run",
            "forecast_id": "base_case",
            "event_name": "soft landing",
            "probability": 0.6,
            "actual_outcome": 1,
            "brier_score": brier_score(0.6, 1),
            "calibration_bucket": bucket_probability(0.6),
        }
    )

    data = list_outcome_dashboard_data()
    summary = outcome_summary()

    assert "opportunity_outcomes" in data
    assert any(row["run_id"] == "test_outcome_run" for row in data["opportunity_outcomes"])
    assert "hit_rate_by_asset_class" in summary
    assert "average_return_by_conviction_bucket" in summary

