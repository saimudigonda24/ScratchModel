import json
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.models import DataSignal
from app.services.env import load_env

load_env()

ROOT = Path(__file__).resolve().parents[3]
CACHE_ROOT = ROOT / "data" / "cache"
RAW_ROOT = ROOT / "data" / "raw_sources"


class MarketDataConnector(ABC):
    """Common interface for live data connectors."""

    source_name: str

    @abstractmethod
    def fetch_signals(self) -> list[DataSignal]:
        """Return normalized macro or market signals."""


class HTTPMarketDataConnector(MarketDataConnector):
    """Shared HTTP connector with retries, cache, raw JSON persistence, and fallback status."""

    cache_ttl_seconds = 60 * 60 * 6
    max_retries = 2
    timeout_seconds = 20

    def real_data_enabled(self) -> bool:
        return os.getenv("HCP_USE_REAL_DATA", "false").lower() == "true"

    def safe_source(self) -> str:
        return "".join(char.lower() if char.isalnum() else "_" for char in self.source_name).strip("_")

    def fetch_json(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        if not self.real_data_enabled():
            return self.unavailable_payload("real data disabled")

        key_payload = {"url": url, "params": params or {}}
        cache_key = str(abs(hash(json.dumps(key_payload, sort_keys=True))))
        cache_path = CACHE_ROOT / self.safe_source() / f"{cache_key}.json"
        if cache_path.exists() and time.time() - cache_path.stat().st_mtime <= self.cache_ttl_seconds:
            return json.loads(cache_path.read_text())

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.get(url, params=params, headers=headers, timeout=self.timeout_seconds)
                response.raise_for_status()
                payload = response.json()
                stamped = {
                    "source": self.source_name,
                    "requested_at": datetime.utcnow().isoformat(),
                    "url": url,
                    "params": params or {},
                    "payload": payload,
                    "cached": False,
                }
                self.save_raw_json(stamped)
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(stamped))
                return stamped
            except Exception as exc:  # pragma: no cover - network dependent
                last_error = str(exc)
                time.sleep(0.25 * (2**attempt))
        return self.unavailable_payload(last_error or "request failed")

    def save_raw_json(self, payload: dict[str, Any]) -> Path:
        path = RAW_ROOT / self.safe_source() / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str))
        return path

    def unavailable_payload(self, reason: str) -> dict[str, Any]:
        payload = {
            "source": self.source_name,
            "requested_at": datetime.utcnow().isoformat(),
            "unavailable": True,
            "reason": reason,
            "payload": {},
        }
        self.save_raw_json(payload)
        return payload

    def unavailable_signal(self, name: str, reason: str) -> DataSignal:
        self.save_raw_json(
            {
                "source": self.source_name,
                "requested_at": datetime.utcnow().isoformat(),
                "unavailable": True,
                "reason": reason,
                "payload": {},
                "signal_name": name,
            }
        )
        return DataSignal(
            source=self.source_name,
            name=name,
            value="unavailable",
            as_of=datetime.utcnow().date().isoformat(),
            direction="neutral",
            interpretation=f"{self.source_name} unavailable: {reason}. No market assumption inferred.",
        )
