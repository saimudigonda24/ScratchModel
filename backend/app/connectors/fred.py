import os
from datetime import datetime
from typing import Any

from app.connectors.base import RAW_ROOT, HTTPMarketDataConnector
from app.models import DataSignal


FRED_SERIES = {
    "CPIAUCSL": "Consumer Price Index",
    "PCEPI": "PCE Price Index",
    "UNRATE": "Unemployment Rate",
    "FEDFUNDS": "Effective Federal Funds Rate",
    "DGS10": "10Y Treasury Yield",
    "T10Y2Y": "10Y-2Y Treasury Spread",
}


class FREDConnector(HTTPMarketDataConnector):
    source_name = "FRED"

    def __init__(self):
        self._last_status: dict[str, Any] | None = None

    def configured(self) -> bool:
        return bool(os.getenv("FRED_API_KEY"))

    def fetch_signals(self) -> list[DataSignal]:
        return self.fetch_series_signals(["CPIAUCSL", "PCEPI", "UNRATE", "FEDFUNDS", "DGS10", "T10Y2Y"])

    def fetch_series_signals(self, series_ids: list[str]) -> list[DataSignal]:
        if not self.configured():
            self._last_status = self._status(False, False, None, "fallback", "missing FRED_API_KEY")
            return [self.unavailable_signal("FRED macro series", "missing FRED_API_KEY")]
        if not self.real_data_enabled():
            self._last_status = self._status(True, False, None, "fallback", "real data disabled; set HCP_USE_REAL_DATA=true")
            return [self.unavailable_signal("FRED macro series", "real data disabled; set HCP_USE_REAL_DATA=true")]

        signals: list[DataSignal] = []
        reachable = False
        latest_successful_pull = None
        errors: list[str] = []
        for series_id in series_ids:
            data = self.fetch_series_observations(series_id, limit=1)
            if data.get("unavailable"):
                reason = data.get("reason", "request unavailable")
                errors.append(reason)
                signals.append(self.unavailable_signal(FRED_SERIES.get(series_id, series_id), reason))
                continue
            obs = data.get("payload", {}).get("observations", [{}])[0]
            value = str(obs.get("value", "unavailable"))
            if value in {".", "", "unavailable"}:
                errors.append(f"{series_id} returned no latest value")
                signals.append(self.unavailable_signal(FRED_SERIES.get(series_id, series_id), f"{series_id} returned no latest value"))
                continue
            reachable = True
            latest_successful_pull = data.get("requested_at") or datetime.utcnow().isoformat()
            signals.append(
                DataSignal(
                    source=self.source_name,
                    name=FRED_SERIES.get(series_id, series_id),
                    value=value,
                    as_of=str(obs.get("date", data.get("requested_at"))),
                    direction="neutral",
                    interpretation=f"Live FRED normalized series {series_id}. Direction should be computed by downstream analytics.",
                )
            )

        mode = "live" if reachable else "fallback"
        reason = "; ".join(dict.fromkeys(errors)) if errors else None
        self._last_status = self._status(True, reachable, latest_successful_pull, mode, reason)
        return signals or [self.unavailable_signal("FRED macro series", reason or "no FRED signals returned")]

    def fetch_series_observations(self, series_id: str, limit: int = 5) -> dict[str, Any]:
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            return self.unavailable_payload("missing FRED_API_KEY")
        return self.fetch_json(
            "https://api.stlouisfed.org/fred/series/observations",
            {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
        )

    def health_status(self) -> dict[str, Any]:
        if self._last_status:
            return dict(self._last_status)
        latest = self.latest_successful_pull()
        return self._status(
            configured=self.configured(),
            reachable=bool(latest),
            latest_successful_pull=latest,
            mode="live" if latest else "fallback",
            reason=None if latest else "not checked yet" if self.configured() else "missing FRED_API_KEY",
        )

    def latest_successful_pull(self) -> str | None:
        source_dir = RAW_ROOT / self.safe_source()
        if not source_dir.exists():
            return None
        latest = None
        for path in sorted(source_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                text = path.read_text()
            except OSError:
                continue
            if '"unavailable": true' in text:
                continue
            latest = datetime.utcfromtimestamp(path.stat().st_mtime).isoformat()
            break
        return latest

    def _status(
        self,
        configured: bool,
        reachable: bool,
        latest_successful_pull: str | None,
        mode: str,
        reason: str | None,
    ) -> dict[str, Any]:
        return {
            "source": self.source_name,
            "configured": configured,
            "reachable": reachable,
            "latest_successful_pull": latest_successful_pull,
            "mode": mode,
            "message": _status_message(configured, reachable, mode, reason),
        }


def _status_message(configured: bool, reachable: bool, mode: str, reason: str | None) -> str:
    if configured and reachable and mode == "live":
        return "Live Data Mode - FRED connected"
    if not configured:
        return "Fallback Mode - FRED_API_KEY is missing"
    return f"Fallback Mode - FRED unavailable: {reason or 'connection not verified'}"
