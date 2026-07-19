from datetime import date
from pathlib import Path

from app.services.backtesting import HistoricalBacktestService
from app.services.database import get_scheduled_job, list_scheduled_jobs, save_opportunity_outcome
from app.services.hedge_evaluator import detect_stress_windows, evaluate_hedge
from app.services.institutional_memory import generate_lessons_learned
from app.services.quality_gates import training_eligibility_gate
from app.services.regime_labeling import RegimeInput, label_regime, save_run_regime_label
from app.services.return_calculator import PricePoint
from app.services.scheduler import LightweightScheduler


def test_durable_job_persistence_and_retry_metadata(tmp_path: Path):
    config = tmp_path / "scheduler.yaml"
    config.write_text(
        "\n".join(
            [
                "jobs:",
                "  - name: phase8_test_job",
                "    cadence: daily",
                "    enabled: true",
                "    max_retries: 1",
                "    target: noop",
                "    command: python -c pass",
            ]
        )
    )
    scheduler = LightweightScheduler(config)
    jobs = list_scheduled_jobs()
    assert any(job["job_name"] == "phase8_test_job" for job in jobs)
    scheduler.set_job_enabled("phase8_test_job", False)
    assert get_scheduled_job("phase8_test_job")["enabled"] == 0


def test_regime_labeling_and_persistence():
    result = label_regime(
        RegimeInput(
            inflation_change=0.8,
            growth_change=-0.5,
            equity_drawdown=-0.15,
            usd_change=0.06,
            credit_spread_change=0.5,
        )
    )
    assert "inflation shock" in result["labels"]
    assert "risk-off" in result["labels"]
    saved = save_run_regime_label("phase8_regime_run", "2024-01-01", RegimeInput(inflation_change=-0.5, growth_change=0.1))
    assert "disinflation" in saved["labels"]


def test_richer_hedge_stress_window_detection():
    equity = [
        PricePoint("2024-01-01", 100),
        PricePoint("2024-01-02", 96),
        PricePoint("2024-01-03", 87),
        PricePoint("2024-01-04", 93),
    ]
    vix = [
        PricePoint("2024-01-01", 15),
        PricePoint("2024-01-02", 20),
        PricePoint("2024-01-03", 23),
    ]
    windows = detect_stress_windows(equity, vix_prices=vix)
    assert any("equity_drawdown" in row["source"] for row in windows)
    assert any("vix_proxy" in row["source"] for row in windows)


def test_hedge_evaluation_reports_stress_metrics():
    hedge_prices = [
        PricePoint("2024-01-01", 100),
        PricePoint("2024-01-02", 101),
        PricePoint("2024-01-03", 105),
        PricePoint("2024-01-04", 104),
    ]
    opportunity_prices = [
        PricePoint("2024-01-01", 100),
        PricePoint("2024-01-02", 96),
        PricePoint("2024-01-03", 88),
        PricePoint("2024-01-04", 90),
    ]
    result = evaluate_hedge(
        "phase8_hedge_run",
        {"name": "Duration hedge", "asset_class": "fixed_income"},
        hedge_prices,
        opportunity_prices,
        "IEF",
    )
    assert "stress-window payoff" in result["notes"]
    assert result["outcome_evaluated"] is True


def test_historical_backtest_summary_formatting():
    service = HistoricalBacktestService()
    result = service.run_backtest_case(date(2024, 1, 1))
    summary = service.format_dashboard_summary(result)
    assert "regime_labels" in summary
    assert "evidence_missed" in summary
    assert summary["available_replay_date"] == "2024-01-01"


def test_lessons_learned_generation_and_quality_gate():
    for index in range(2):
        save_opportunity_outcome(
            {
                "run_id": f"phase8_lesson_{index}",
                "idea_id": f"Miss {index}",
                "asset_class": "equity",
                "instrument": "SPY",
                "proxy_ticker": "SPY",
                "thesis_fit": "Test",
                "start_date": "2024-01-01",
                "target_horizon_months": [7, 14],
                "benchmark": "IEF",
                "expected_direction": "long",
                "expected_catalyst": "Test",
                "invalidation_trigger": "Test",
                "conviction_score": 8,
                "realized_return": -0.1,
                "benchmark_return": 0.02,
                "max_drawdown": -0.2,
                "volatility": 0.2,
                "hit_miss_label": "miss",
                "outcome_evaluated": True,
                "outcome_quality_score": 5,
                "eligible_for_fine_tuning": False,
            }
        )
    lessons = generate_lessons_learned(min_count=2)
    assert lessons["created"] >= 1
    gate = training_eligibility_gate(
        {
            "approval_status": "approved",
            "evidence": ["Data"],
            "risks": ["Risk"],
            "proxy_ticker": "SPY",
            "outcome_evaluated": True,
            "regime_labels": ["soft landing"],
            "quality_score": 8,
            "repeated_failure_pattern": True,
        }
    )
    assert gate["eligible_for_fine_tuning"] is False
    assert "failure_pattern_allowed" in gate["explanation"]
