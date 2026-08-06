"""Verify live FRED connectivity without printing or storing secrets."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectors.fred import FRED_SERIES  # noqa: E402
from app.services.env import load_env  # noqa: E402
from app.services.market_data import MarketDataService  # noqa: E402


def main() -> int:
    load_env()
    os.environ["HCP_USE_REAL_DATA"] = "true"
    service = MarketDataService()
    signals = service.fred.fetch_series_signals(list(FRED_SERIES))
    status = service.fred_status()

    print(status["message"])
    print(f"configured={status['configured']} reachable={status['reachable']} mode={status['mode']}")
    print(f"latest_successful_pull={status.get('latest_successful_pull') or 'never'}")
    for signal in signals:
        print(f"{signal.name}: {signal.value} as_of={signal.as_of}")

    if not status["configured"]:
        print("Add FRED_API_KEY to local .env. Do not commit .env.")
        return 0
    if not status["reachable"]:
        print("FRED was configured but not reachable. Check the key, network, or FRED API status.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
