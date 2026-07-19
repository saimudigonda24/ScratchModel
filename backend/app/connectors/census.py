from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class CensusConnector(HTTPMarketDataConnector):
    source_name = "Census Bureau"

    def fetch_signals(self) -> list[DataSignal]:
        data = self.fetch_json(
            "https://api.census.gov/data/timeseries/eits/marts",
            {"get": "cell_value,time_slot_id", "for": "us:*", "NAICS": "44X72"},
        )
        if data.get("unavailable"):
            return [self.unavailable_signal("Retail Sales", data.get("reason", "request unavailable"))]
        try:
            rows = data["payload"]
            latest = rows[-1]
            return [
                DataSignal(
                    source=self.source_name,
                    name="Retail Sales",
                    value=str(latest[0]),
                    as_of=str(latest[1]),
                    direction="neutral",
                    interpretation="Census normalized retail-sales series.",
                )
            ]
        except Exception as exc:
            return [self.unavailable_signal("Retail Sales", f"normalization failed: {exc}")]

