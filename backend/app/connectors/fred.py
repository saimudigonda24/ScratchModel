import os

from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class FREDConnector(HTTPMarketDataConnector):
    source_name = "FRED"

    def fetch_signals(self) -> list[DataSignal]:
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            return [self.unavailable_signal("FRED rates and inflation series", "missing FRED_API_KEY")]
        signals: list[DataSignal] = []
        for series_id, name in [("DGS10", "10Y Treasury Yield"), ("PCEPI", "PCE Price Index")]:
            data = self.fetch_json(
                "https://api.stlouisfed.org/fred/series/observations",
                {"series_id": series_id, "api_key": api_key, "file_type": "json", "sort_order": "desc", "limit": 1},
            )
            if data.get("unavailable"):
                signals.append(self.unavailable_signal(name, data.get("reason", "request unavailable")))
                continue
            obs = data.get("payload", {}).get("observations", [{}])[0]
            signals.append(
                DataSignal(
                    source=self.source_name,
                    name=name,
                    value=str(obs.get("value", "unavailable")),
                    as_of=str(obs.get("date", data.get("requested_at"))),
                    direction="neutral",
                    interpretation=f"Live FRED normalized series {series_id}. Direction should be computed by downstream analytics.",
                )
            )
        return signals

