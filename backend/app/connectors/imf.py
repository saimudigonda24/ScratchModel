from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class IMFConnector(HTTPMarketDataConnector):
    source_name = "IMF"

    def fetch_signals(self) -> list[DataSignal]:
        data = self.fetch_json("https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH")
        if data.get("unavailable"):
            return [self.unavailable_signal("IMF Real GDP Growth", data.get("reason", "request unavailable"))]
        try:
            values = data.get("payload", {}).get("values", {}).get("NGDP_RPCH", {})
            world = values.get("WEO") or values.get("001") or {}
            latest_year = sorted(world.keys())[-1]
            return [
                DataSignal(
                    source=self.source_name,
                    name="IMF Real GDP Growth",
                    value=str(world[latest_year]),
                    as_of=str(latest_year),
                    direction="neutral",
                    interpretation="IMF normalized global growth indicator.",
                )
            ]
        except Exception as exc:
            return [self.unavailable_signal("IMF Real GDP Growth", f"normalization failed: {exc}")]

