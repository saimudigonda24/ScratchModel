from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class CMEFedWatchConnector(HTTPMarketDataConnector):
    source_name = "CME FedWatch"

    def fetch_signals(self) -> list[DataSignal]:
        return [
            self.unavailable_signal(
                "FedWatch implied policy probabilities",
                "CME does not provide a stable unauthenticated JSON API in this starter; add licensed/approved endpoint when available",
            )
        ]

