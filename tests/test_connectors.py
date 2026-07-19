import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectors.fred import FREDConnector
from app.connectors.sec_edgar import SECEdgarConnector
from app.connectors.world_bank import WorldBankConnector
from app.connectors.yahoo_finance import YahooFinanceConnector
from app.services.market_data import MarketDataService


def test_connectors_have_mock_fallback(monkeypatch):
    monkeypatch.setenv("HCP_USE_REAL_DATA", "false")
    connectors = [FREDConnector(), YahooFinanceConnector(), SECEdgarConnector(), WorldBankConnector()]

    for connector in connectors:
        signals = connector.fetch_signals()
        assert signals
        assert signals[0].source == connector.source_name


def test_market_data_service_exposes_domain_methods(monkeypatch):
    monkeypatch.setenv("HCP_USE_REAL_DATA", "false")
    service = MarketDataService()

    assert service.get_growth_data()
    assert service.get_inflation_data()
    assert service.get_rates_data()
    assert service.get_labor_data()
    assert service.get_credit_data()
    assert service.get_equity_data()
    assert service.get_fx_data()
    assert service.get_commodity_data()
    assert service.get_crypto_data()
    assert service.get_global_macro_data()

    snapshot = service.get_all_data()
    assert snapshot.signals
    assert snapshot.source_status
