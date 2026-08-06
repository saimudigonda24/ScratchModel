import os

from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


BLS_SERIES = {
    "CUUR0000SA0": "Consumer Price Index",
    "WPUFD4": "Producer Price Index Final Demand",
    "CES0000000001": "Nonfarm Payrolls",
}


class BLSConnector(HTTPMarketDataConnector):
    source_name = "BLS"

    def fetch_signals(self) -> list[DataSignal]:
        signals: list[DataSignal] = []
        for series_id, name in BLS_SERIES.items():
            signals.append(self.fetch_series_signal(series_id, name))
        return signals

    def fetch_series_signal(self, series_id: str, name: str) -> DataSignal:
        params = {"latest": "true"}
        api_key = os.getenv("BLS_API_KEY")
        if api_key:
            params["registrationkey"] = api_key
        data = self.fetch_json(f"https://api.bls.gov/publicAPI/v2/timeseries/data/{series_id}", params)
        if data.get("unavailable"):
            return self.unavailable_signal(name, data.get("reason", "request unavailable"))
        try:
            payload = data["payload"]
            if payload.get("status") not in {None, "REQUEST_SUCCEEDED"}:
                messages = "; ".join(payload.get("message", [])) or payload.get("status")
                return self.unavailable_signal(name, messages)
            item = payload["Results"]["series"][0]["data"][0]
            return DataSignal(
                source=self.source_name,
                name=name,
                value=str(item["value"]),
                as_of=f"{item['year']} {item['periodName']}",
                direction="neutral",
                interpretation=f"BLS normalized live series {series_id}. Direction should be computed by downstream analytics.",
            )
        except Exception as exc:
            return self.unavailable_signal(name, f"normalization failed: {exc}")
