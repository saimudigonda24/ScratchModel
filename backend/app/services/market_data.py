from app.connectors.bea import BEAConnector
from app.connectors.bls import BLSConnector
from app.connectors.census import CensusConnector
from app.connectors.cme_fedwatch import CMEFedWatchConnector
from app.connectors.fred import FREDConnector
from app.connectors.imf import IMFConnector
from app.connectors.sec_edgar import SECEdgarConnector
from app.connectors.trading_economics import TradingEconomicsConnector
from app.connectors.world_bank import WorldBankConnector
from app.connectors.yahoo_finance import YahooFinanceConnector
from app.models import DataSignal, MacroDataSnapshot


class MarketDataService:
    """Single interface between research agents and external market data sources."""

    def __init__(self):
        self.fred = FREDConnector()
        self.bls = BLSConnector()
        self.bea = BEAConnector()
        self.census = CensusConnector()
        self.cme = CMEFedWatchConnector()
        self.yahoo = YahooFinanceConnector()
        self.sec = SECEdgarConnector()
        self.world_bank = WorldBankConnector()
        self.imf = IMFConnector()
        self.trading_economics = TradingEconomicsConnector()

    def _collect(self, connectors) -> list[DataSignal]:
        signals: list[DataSignal] = []
        for connector in connectors:
            signals.extend(connector.fetch_signals())
        return signals

    def get_growth_data(self) -> list[DataSignal]:
        return self._collect([self.bea, self.world_bank, self.imf, self.trading_economics])

    def get_inflation_data(self) -> list[DataSignal]:
        return self._collect([self.fred, self.trading_economics])

    def get_rates_data(self) -> list[DataSignal]:
        return self._collect([self.fred, self.cme])

    def get_labor_data(self) -> list[DataSignal]:
        return self._collect([self.bls])

    def get_credit_data(self) -> list[DataSignal]:
        return self._collect([self.fred, self.sec])

    def get_equity_data(self) -> list[DataSignal]:
        return self._collect([self.yahoo, self.sec])

    def get_fx_data(self) -> list[DataSignal]:
        return self._collect([self.trading_economics, self.fred])

    def get_commodity_data(self) -> list[DataSignal]:
        return self._collect([self.trading_economics, self.imf])

    def get_crypto_data(self) -> list[DataSignal]:
        return [
            DataSignal(
                source="Market Data Service",
                name="Crypto data",
                value="unavailable",
                as_of="latest",
                direction="neutral",
                interpretation="No approved crypto connector configured yet. Add a licensed connector before using crypto data in production.",
            )
        ]

    def get_global_macro_data(self) -> list[DataSignal]:
        return self._collect([self.world_bank, self.imf, self.trading_economics])

    def get_all_data(self) -> MacroDataSnapshot:
        connectors = [
            self.fred,
            self.bls,
            self.bea,
            self.census,
            self.cme,
            self.yahoo,
            self.sec,
            self.world_bank,
            self.imf,
            self.trading_economics,
        ]
        signals: list[DataSignal] = []
        source_status: dict[str, str] = {}
        for connector in connectors:
            try:
                connector_signals = connector.fetch_signals()
                signals.extend(connector_signals)
                unavailable = [signal for signal in connector_signals if signal.value == "unavailable"]
                source_status[connector.source_name] = (
                    f"unavailable: {len(unavailable)}/{len(connector_signals)} signals"
                    if unavailable
                    else f"ok: {len(connector_signals)} signals"
                )
            except Exception as exc:  # pragma: no cover - defensive boundary
                source_status[connector.source_name] = f"error: {exc}"
        return MacroDataSnapshot(signals=signals, source_status=source_status)

