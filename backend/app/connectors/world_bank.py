from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class WorldBankConnector(HTTPMarketDataConnector):
    source_name = "World Bank"

    def fetch_signals(self) -> list[DataSignal]:
        data = self.fetch_json(
            "https://api.worldbank.org/v2/country/WLD/indicator/NY.GDP.MKTP.KD.ZG",
            {"format": "json", "per_page": 2},
        )
        if data.get("unavailable"):
            return [self.unavailable_signal("World real GDP growth", data.get("reason", "request unavailable"))]
        try:
            rows = data["payload"][1]
            latest = next(row for row in rows if row.get("value") is not None)
            return [
                DataSignal(
                    source=self.source_name,
                    name="World Real GDP Growth",
                    value=f"{float(latest['value']):.2f}% YoY",
                    as_of=str(latest["date"]),
                    direction="neutral",
                    interpretation="World Bank normalized global growth series.",
                )
            ]
        except Exception as exc:
            return [self.unavailable_signal("World real GDP growth", f"normalization failed: {exc}")]

