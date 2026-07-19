import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.calibration_report import generate_calibration_report
from app.services.database import list_scheduled_job_runs, outcome_summary
from app.services.fine_tuning_readiness import fine_tuning_readiness_report
from app.services.hedge_evaluator import detect_stress_windows, evaluate_hedge
from app.services.return_calculator import PricePoint
from app.services.scheduler import LightweightScheduler, load_scheduler_config
from app.services.thesis_outcome_evaluator import save_thesis_score, score_thesis_outcome


def test_scheduler_config_loading_and_registration():
    jobs = load_scheduler_config()
    scheduler = LightweightScheduler()
    results = scheduler.run_once(dry_run=True)
    runs = list_scheduled_job_runs(10)

    assert any(job.name == "daily_price_ingestion" for job in jobs)
    assert scheduler.enabled_jobs()
    assert results
    assert runs


def test_thesis_outcome_scoring_and_persistence():
    thesis = {"title": "Soft landing", "horizon_months": [7, 14]}
    payload = score_thesis_outcome(
        "thesis_test_run",
        thesis,
        {
            "start_date": "2024-01-01",
            "growth_call_accuracy": 8,
            "inflation_call_accuracy": 7,
            "central_bank_reaction_accuracy": 6,
            "country_overlay_accuracy": 5,
            "probability_band_accuracy": 7,
            "key_invalidation_trigger_accuracy": 8,
            "narrative_quality_after_fact": 7,
        },
    )
    saved = save_thesis_score("thesis_test_run", thesis, payload["outcome"] | {"start_date": "2024-01-01"})

    assert payload["outcome"]["overall_thesis_score"] > 0
    assert saved["outcome"]["overall_thesis_score"] > 0


def test_hedge_stress_window_evaluation():
    opportunity_prices = [
        PricePoint("2024-01-01", 100),
        PricePoint("2024-02-01", 85),
        PricePoint("2024-03-01", 90),
    ]
    hedge_prices = [
        PricePoint("2024-01-01", 100),
        PricePoint("2024-02-01", 110),
        PricePoint("2024-03-01", 108),
    ]
    hedge = {"name": "Gold hedge", "asset_class": "commodity", "expected_horizon_months": [7, 14]}

    windows = detect_stress_windows(opportunity_prices)
    result = evaluate_hedge("hedge_test_run", hedge, hedge_prices, opportunity_prices, "GLD")

    assert windows
    assert result["hedge_effectiveness"] > 0
    assert result["outcome_evaluated"] is True


def test_calibration_report_generation_and_readiness_summary():
    report = generate_calibration_report()
    readiness = fine_tuning_readiness_report(minimum_examples=10)
    summary = outcome_summary()

    assert Path(report["path"]).exists()
    assert "hit_rate_by_asset_class" in report
    assert "recommendation" in readiness
    assert "hit_rate" in summary

