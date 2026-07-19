import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.services.database import save_daily_prices

ROOT = Path(__file__).resolve().parents[3]
RAW_PRICE_ROOT = ROOT / "data" / "raw_prices"


def _unix(date_text: str) -> int:
    return int(datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc).timestamp())


class PriceIngestionService:
    source = "Yahoo Finance"

    def save_raw_response(self, ticker: str, payload: dict) -> Path:
        safe_ticker = ticker.replace("/", "_")
        path = RAW_PRICE_ROOT / safe_ticker / f"{datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str))
        return path

    def normalize_yahoo_chart(self, ticker: str, payload: dict) -> list[dict]:
        result = payload.get("chart", {}).get("result", [])
        if not result:
            return []
        chart = result[0]
        timestamps = chart.get("timestamp", [])
        quote = chart.get("indicators", {}).get("quote", [{}])[0]
        adjclose = chart.get("indicators", {}).get("adjclose", [{}])[0].get("adjclose", [])
        rows: list[dict] = []
        for index, timestamp in enumerate(timestamps):
            close = (quote.get("close") or [None])[index]
            if close is None:
                continue
            row = {
                "date": datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat(),
                "open": (quote.get("open") or [None])[index],
                "high": (quote.get("high") or [None])[index],
                "low": (quote.get("low") or [None])[index],
                "close": close,
                "adj_close": adjclose[index] if index < len(adjclose) else close,
                "volume": (quote.get("volume") or [None])[index],
                "raw": {"ticker": ticker, "timestamp": timestamp},
            }
            rows.append(row)
        return rows

    def fetch_yahoo_prices(self, ticker: str, start_date: str, end_date: str) -> list[dict]:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {"period1": _unix(start_date), "period2": _unix(end_date), "interval": "1d", "events": "history"}
        try:
            response = httpx.get(url, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            self.save_raw_response(ticker, payload)
            return self.normalize_yahoo_chart(ticker, payload)
        except Exception as exc:
            payload = {"ticker": ticker, "unavailable": True, "reason": str(exc), "requested_at": datetime.utcnow().isoformat()}
            self.save_raw_response(ticker, payload)
            return []

    def ingest_prices(self, tickers: list[str], start_date: str, end_date: str) -> dict:
        summary = {"source": self.source, "start_date": start_date, "end_date": end_date, "tickers": {}}
        for ticker in tickers:
            rows = self.fetch_yahoo_prices(ticker, start_date, end_date)
            inserted = save_daily_prices(ticker, rows, self.source) if rows else 0
            summary["tickers"][ticker] = {"rows": len(rows), "inserted": inserted}
        return summary

