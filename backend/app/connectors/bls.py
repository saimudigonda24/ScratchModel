from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class BLSConnector(HTTPMarketDataConnector):
    source_name = "BLS"

    def fetch_signals(self) -> list[DataSignal]:
        data = self.fetch_json(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000",
            {"latest": "true"},
        )
        if data.get("unavailable"):
            return [self.unavailable_signal("Unemployment Rate", data.get("reason", "request unavailable"))]
        try:
            item = data["payload"]["Results"]["series"][0]["data"][0]
            return [
                DataSignal(
                    source=self.source_name,
                    name="Unemployment Rate",
                    value=f"{item['value']}%",
                    as_of=f"{item['year']} {item['periodName']}",
                    direction="neutral",
                    interpretation="BLS normalized unemployment rate series.",
                )
            ]
        except Exception as exc:
            return [self.unavailable_signal("Unemployment Rate", f"normalization failed: {exc}")]

