import os

from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


class SECEdgarConnector(HTTPMarketDataConnector):
    source_name = "SEC EDGAR"

    def fetch_signals(self) -> list[DataSignal]:
        user_agent = os.getenv("SEC_USER_AGENT")
        if not user_agent:
            return [self.unavailable_signal("SEC filings", "missing SEC_USER_AGENT")]
        data = self.fetch_json(
            "https://data.sec.gov/submissions/CIK0000320193.json",
            headers={"User-Agent": user_agent},
        )
        if data.get("unavailable"):
            return [self.unavailable_signal("SEC filings", data.get("reason", "request unavailable"))]
        filings = data.get("payload", {}).get("filings", {}).get("recent", {})
        form = (filings.get("form") or ["unavailable"])[0]
        filing_date = (filings.get("filingDate") or [data.get("requested_at")])[0]
        return [
            DataSignal(
                source=self.source_name,
                name="Recent Large-Cap Filing Activity",
                value=str(form),
                as_of=str(filing_date),
                direction="neutral",
                interpretation="SEC EDGAR normalized filing availability signal. Filing text analysis belongs in downstream research parsing.",
            )
        ]

