import contextlib
import io

from app.connectors.base import HTTPMarketDataConnector
from app.models import DataSignal


YAHOO_TICKERS = ["SPY", "GLD", "TLT", "BTC-USD"]


class YahooFinanceConnector(HTTPMarketDataConnector):
    source_name = "Yahoo Finance"

    def fetch_signals(self) -> list[DataSignal]:
        yfinance_signals = self.fetch_yfinance_signals()
        if yfinance_signals:
            return yfinance_signals
        return [self.fetch_chart_signal("%5EGSPC", "S&P 500 5D Momentum")]

    def fetch_yfinance_signals(self) -> list[DataSignal]:
        if not self.real_data_enabled():
            return []
        try:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                import yfinance as yf
        except Exception:
            return []

        signals: list[DataSignal] = []
        for ticker in YAHOO_TICKERS:
            try:
                with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                    history = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
                closes = history["Close"].dropna()
                if len(closes) < 2:
                    signals.append(self.unavailable_signal(ticker, "insufficient yfinance close history"))
                    continue
                latest = float(closes.iloc[-1])
                previous = float(closes.iloc[-2])
                change = (latest / previous - 1) * 100
                signals.append(
                    DataSignal(
                        source=self.source_name,
                        name=f"{ticker} 5D Momentum",
                        value=f"{change:.2f}%",
                        as_of=str(closes.index[-1].date()),
                        direction="improving" if change >= 0 else "deteriorating",
                        interpretation=f"Yahoo Finance yfinance normalized market proxy for {ticker}.",
                    )
                )
            except Exception as exc:
                signals.append(self.unavailable_signal(ticker, f"yfinance normalization failed: {exc.__class__.__name__}"))
        if any(signal.value != "unavailable" for signal in signals):
            self.save_raw_json(
                {
                    "source": self.source_name,
                    "provider": "yfinance",
                    "tickers": YAHOO_TICKERS,
                    "signals": [signal.model_dump(mode="json") for signal in signals],
                }
            )
        return signals

    def fetch_chart_signal(self, ticker: str, name: str) -> DataSignal:
        data = self.fetch_json(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
            {"range": "5d", "interval": "1d"},
        )
        if data.get("unavailable"):
            return self.unavailable_signal(name, data.get("reason", "request unavailable"))
        try:
            result = data["payload"]["chart"]["result"][0]
            closes = result["indicators"]["quote"][0]["close"]
            latest = next(value for value in reversed(closes) if value is not None)
            previous = next(value for value in reversed(closes[:-1]) if value is not None)
            change = (latest / previous - 1) * 100
            return DataSignal(
                source=self.source_name,
                name=name,
                value=f"{change:.2f}%",
                as_of=str(data.get("requested_at")),
                direction="improving" if change >= 0 else "deteriorating",
                interpretation="Yahoo Finance normalized market momentum proxy.",
            )
        except Exception as exc:
            return self.unavailable_signal(name, f"normalization failed: {exc}")
