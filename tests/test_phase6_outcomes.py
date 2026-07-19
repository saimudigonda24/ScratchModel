import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.automated_outcome_evaluator import AutomatedOutcomeEvaluator
from app.services.backtesting import HistoricalBacktestService
from app.services.database import (
    connect,
    init_db,
    load_proxy_override,
    save_daily_prices,
    save_proxy_override,
)
from app.services.price_ingestion import PriceIngestionService


def _price_rows(start_price: float, end_price: float):
    return [
        {"date": "2024-01-01", "close": start_price, "adj_close": start_price, "raw": {}},
        {"date": "2024-08-15", "close": end_price, "adj_close": end_price, "raw": {}},
    ]


def test_price_ingestion_normalization_and_duplicate_prevention():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704067200, 1704153600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [99, 100],
                                "high": [101, 102],
                                "low": [98, 99],
                                "close": [100, 101],
                                "volume": [1_000, 1_100],
                            }
                        ],
                        "adjclose": [{"adjclose": [100, 101]}],
                    },
                }
            ]
        }
    }
    rows = PriceIngestionService().normalize_yahoo_chart("TEST", payload)
    first = save_daily_prices("TEST", rows, "test")
    second = save_daily_prices("TEST", rows, "test")

    assert len(rows) == 2
    assert rows[0]["adj_close"] == 100
    assert first >= 0
    assert second == 0


def test_manual_proxy_override_save_load():
    payload = {
        "run_id": "override_run",
        "item_type": "opportunity",
        "item_id": "Quality equities",
        "proxy_ticker": "QUAL",
        "benchmark_ticker": "SPY",
        "expected_direction": "long",
        "start_date": "2024-01-01",
        "target_horizon_months": [7, 14],
        "notes": "manual test",
    }
    save_proxy_override(payload)
    loaded = load_proxy_override("override_run", "opportunity", "Quality equities")

    assert loaded
    assert loaded["proxy_ticker"] == "QUAL"
    assert loaded["target_horizon_months"] == [7, 14]


def test_automated_outcome_evaluation_and_eligibility():
    init_db()
    run_id = "phase6_eval_run"
    idea = {
        "name": "Quality equities",
        "asset_class": "equity",
        "thesis_fit": "Fits soft landing",
        "expected_horizon_months": [7, 14],
        "catalyst": "EPS improves",
        "invalidating_data": ["spreads widen"],
        "evidence": ["EPS revisions"],
        "risks": ["hard landing"],
    }
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO macro_reports (run_id, title, content, created_at, training_approved) VALUES (?, ?, ?, ?, 1)",
            (run_id, "test", "content", "2024-01-01T00:00:00",),
        )
        conn.execute(
            "INSERT INTO opportunities (run_id, name, asset_class, conviction_score, approval_status, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, "Quality equities", "equity", 7.0, "approved", json.dumps(idea), "2024-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    save_proxy_override(
        {
            "run_id": run_id,
            "item_type": "opportunity",
            "item_id": "Quality equities",
            "proxy_ticker": "QUAL",
            "benchmark_ticker": "SPY",
            "expected_direction": "long",
            "start_date": "2024-01-01",
            "target_horizon_months": [7, 14],
            "notes": "test override",
        }
    )
    save_daily_prices("QUAL", _price_rows(100, 120), "Yahoo Finance")
    save_daily_prices("SPY", _price_rows(100, 105), "Yahoo Finance")

    result = AutomatedOutcomeEvaluator().evaluate(as_of="2024-08-15")

    assert result["evaluated"] >= 1
    detail = next(item for item in result["details"] if item.get("idea") == "Quality equities")
    assert detail["hit_miss_label"] == "hit"


def test_backtest_outcome_comparison_uses_stored_prices():
    save_daily_prices("IEF", _price_rows(100, 110), "Yahoo Finance")
    save_daily_prices("SPY", _price_rows(100, 105), "Yahoo Finance")

    outcomes = HistoricalBacktestService().compare_stored_proxy_outcomes("2024-01-01", "IEF", "SPY", "2024-08-15")

    assert outcomes
    assert round(outcomes[0]["total_return"], 4) == 0.1
    assert round(outcomes[0]["benchmark_return"], 4) == 0.05

