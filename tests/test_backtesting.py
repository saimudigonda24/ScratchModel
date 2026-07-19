import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.backtesting import HISTORICAL_TEST_DATES, HistoricalBacktestService


def test_historical_backtest_scaffold(monkeypatch):
    monkeypatch.setenv("HCP_USE_REAL_DATA", "false")
    service = HistoricalBacktestService()

    snapshot = service.point_in_time_snapshot(date(2023, 3, 1))
    suite = service.run_standard_suite()

    assert snapshot.signals
    assert len(suite) == len(HISTORICAL_TEST_DATES)
    assert "probability_calibration" in suite[0]

