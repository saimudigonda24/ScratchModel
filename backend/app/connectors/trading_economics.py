import os

from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class TradingEconomicsConnector(HTTPMarketDataConnector):
    source_name = "TradingEconomics"

    def fetch_signals(self) -> list[DataSignal]:
        api_key = os.getenv("TRADING_ECONOMICS_API_KEY")
        if not api_key:
            return [self.unavailable_signal("TradingEconomics calendar", "missing TRADING_ECONOMICS_API_KEY")]
        data = self.fetch_json(
            "https://api.tradingeconomics.com/calendar/country/united%20states",
            {"c": api_key, "format": "json"},
        )
        if data.get("unavailable"):
            return [self.unavailable_signal("TradingEconomics calendar", data.get("reason", "request unavailable"))]
        payload = data.get("payload", [])
        return [
            DataSignal(
                source=self.source_name,
                name="TradingEconomics US Calendar Events",
                value=str(len(payload)),
                as_of=str(data.get("requested_at")),
                direction="neutral",
                interpretation="TradingEconomics normalized count of retrieved US macro calendar events.",
            )
        ]

