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


def test_fred_missing_key_reports_fallback(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("HCP_USE_REAL_DATA", "true")
    connector = FREDConnector()

    signals = connector.fetch_signals()
    status = connector.health_status()

    assert signals[0].value == "unavailable"
    assert status["configured"] is False
    assert status["reachable"] is False
    assert "FRED_API_KEY" in status["message"]


def test_fred_invalid_key_reports_safe_fallback(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "invalid-secret-value")
    monkeypatch.setenv("HCP_USE_REAL_DATA", "true")
    connector = FREDConnector()

    def fake_fetch_json(url, params=None, headers=None):
        return connector.unavailable_payload("HTTP 400 from FRED")

    monkeypatch.setattr(connector, "fetch_json", fake_fetch_json)
    signals = connector.fetch_series_signals(["CPIAUCSL"])
    status = connector.health_status()

    assert signals[0].value == "unavailable"
    assert status["configured"] is True
    assert status["reachable"] is False
    assert "invalid-secret-value" not in status["message"]


def test_fred_valid_mocked_response(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "secret-test-key")
    monkeypatch.setenv("HCP_USE_REAL_DATA", "true")
    connector = FREDConnector()

    def fake_fetch_json(url, params=None, headers=None):
        return {
            "source": "FRED",
            "requested_at": "2026-08-06T00:00:00",
            "params": {"api_key": "[REDACTED]", "series_id": params["series_id"]},
            "payload": {"observations": [{"date": "2026-07-01", "value": "3.1"}]},
        }

    monkeypatch.setattr(connector, "fetch_json", fake_fetch_json)
    signals = connector.fetch_series_signals(["CPIAUCSL"])
    status = connector.health_status()

    assert signals[0].name == "Consumer Price Index"
    assert signals[0].value == "3.1"
    assert status["configured"] is True
    assert status["reachable"] is True
    assert status["message"] == "Live Data Mode - FRED connected"


def test_fred_key_is_redacted_from_persisted_params(monkeypatch, tmp_path):
    monkeypatch.setenv("FRED_API_KEY", "super-secret-fred-key")
    connector = FREDConnector()

    sanitized = connector.sanitize_mapping({"api_key": "super-secret-fred-key", "series_id": "CPIAUCSL"})

    assert sanitized["api_key"] == "[REDACTED]"
    assert "super-secret-fred-key" not in str(sanitized)


def test_fred_status_formatting_for_live_and_fallback(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "configured-key")
    connector = FREDConnector()

    live = connector._status(True, True, "2026-08-06T00:00:00", "live", None)
    fallback = connector._status(True, False, None, "fallback", "HTTP 400 from FRED")

    assert live["message"] == "Live Data Mode - FRED connected"
    assert fallback["message"].startswith("Fallback Mode")
    assert "configured-key" not in str(live)
    assert "configured-key" not in str(fallback)
