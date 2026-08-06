import os

from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


BEA_SERIES = [
    {
        "name": "Real GDP",
        "table": "T10101",
        "line_number": "1",
        "interpretation": "BEA normalized live NIPA real GDP table data.",
    },
    {
        "name": "Personal Income",
        "table": "T20600",
        "line_number": "1",
        "interpretation": "BEA normalized live NIPA personal income table data.",
    },
]


class BEAConnector(HTTPMarketDataConnector):
    source_name = "BEA"

    def fetch_signals(self) -> list[DataSignal]:
        return [self.fetch_nipa_signal(spec) for spec in BEA_SERIES]

    def fetch_nipa_signal(self, spec: dict) -> DataSignal:
        params = {
            "UserID": os.getenv("BEA_API_KEY", ""),
            "method": "GetData",
            "datasetname": "NIPA",
            "TableName": spec["table"],
            "Frequency": "Q",
            "Year": "X",
            "ResultFormat": "JSON",
        }
        if spec.get("line_number"):
            params["LineNumber"] = spec["line_number"]
        data = self.fetch_json("https://apps.bea.gov/api/data", params)
        if data.get("unavailable"):
            return self.unavailable_signal(spec["name"], data.get("reason", "request unavailable"))
        try:
            payload = data["payload"].get("BEAAPI", {})
            if payload.get("Error"):
                return self.unavailable_signal(spec["name"], str(payload["Error"].get("APIErrorDescription", payload["Error"])))
            rows = payload["Results"]["Data"]
            latest = rows[0]
            return DataSignal(
                source=self.source_name,
                name=spec["name"],
                value=str(latest.get("DataValue", "unavailable")),
                as_of=str(latest.get("TimePeriod", data.get("requested_at"))),
                direction="neutral",
                interpretation=spec["interpretation"],
            )
        except Exception as exc:
            return self.unavailable_signal(spec["name"], f"normalization failed: {exc}")
