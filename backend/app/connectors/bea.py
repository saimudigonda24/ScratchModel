import os

from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class BEAConnector(HTTPMarketDataConnector):
    source_name = "BEA"

    def fetch_signals(self) -> list[DataSignal]:
        params = {
            "UserID": os.getenv("BEA_API_KEY", ""),
            "method": "GetData",
            "datasetname": "NIPA",
            "TableName": "T10101",
            "Frequency": "Q",
            "Year": "X",
            "ResultFormat": "JSON",
        }
        data = self.fetch_json("https://apps.bea.gov/api/data", params)
        if data.get("unavailable"):
            return [self.unavailable_signal("Real GDP Growth", data.get("reason", "request unavailable"))]
        try:
            rows = data["payload"]["BEAAPI"]["Results"]["Data"]
            latest = rows[0]
            return [
                DataSignal(
                    source=self.source_name,
                    name="Real GDP Growth",
                    value=str(latest.get("DataValue", "unavailable")),
                    as_of=str(latest.get("TimePeriod", data.get("requested_at"))),
                    direction="neutral",
                    interpretation="BEA normalized NIPA GDP growth data.",
                )
            ]
        except Exception as exc:
            return [self.unavailable_signal("Real GDP Growth", f"normalization failed: {exc}")]

