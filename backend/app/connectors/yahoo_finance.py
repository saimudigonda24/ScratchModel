from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class YahooFinanceConnector(HTTPMarketDataConnector):
    source_name = "Yahoo Finance"

    def fetch_signals(self) -> list[DataSignal]:
        data = self.fetch_json(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC",
            {"range": "5d", "interval": "1d"},
        )
        if data.get("unavailable"):
            return [self.unavailable_signal("S&P 500 market data", data.get("reason", "request unavailable"))]
        try:
            result = data["payload"]["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            latest = next(value for value in reversed(closes) if value is not None)
            previous = next(value for value in reversed(closes[:-1]) if value is not None)
            change = (latest / previous - 1) * 100
            return [
                DataSignal(
                    source=self.source_name,
                    name="S&P 500 5D Momentum",
                    value=f"{change:.2f}%",
                    as_of=str(data.get("requested_at")),
                    direction="improving" if change >= 0 else "deteriorating",
                    interpretation="Yahoo Finance normalized equity momentum proxy.",
                )
            ]
        except Exception as exc:
            return [self.unavailable_signal("S&P 500 market data", f"normalization failed: {exc}")]

