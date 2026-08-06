import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectors.fred import FREDConnector
from app.services.llm import OpenAIClient
from app.services import source_status
from app.services.source_status import audit_sources, scenario_comparison_readiness, test_source as run_source_test


SECRET_ENV_VARS = [
    "FRED_API_KEY",
    "BLS_API_KEY",
    "BEA_API_KEY",
    "CENSUS_API_KEY",
    "TRADING_ECONOMICS_API_KEY",
    "SEC_USER_AGENT",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
]


def isolate_source_files(monkeypatch, tmp_path):
    monkeypatch.setattr(source_status, "RAW_ROOT", tmp_path)
    import app.connectors.fred as fred_module

    monkeypatch.setattr(fred_module, "RAW_ROOT", tmp_path)


def record_named(audit: dict, name: str) -> dict:
    return next(row for row in audit["records"] if row["source_name"] == name)


def test_source_audit_missing_keys_are_safe_and_actionable(monkeypatch, tmp_path):
    isolate_source_files(monkeypatch, tmp_path)
    for env_var in SECRET_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)
    monkeypatch.setenv("HCP_USE_REAL_LLM", "false")

    audit = audit_sources(test_connections=False)
    fred = record_named(audit, "FRED")
    openai = record_named(audit, "OpenAI")

    assert fred["mode"] == "Key Needed"
    assert fred["configured"] is False
    assert "FRED_API_KEY" in fred["action_needed"]
    assert openai["mode"] == "Key Needed"
    assert "OPENAI_API_KEY" in openai["action_needed"]
    assert "records" in audit
    assert "comparison_readiness" in audit


def test_source_audit_does_not_leak_secret_values(monkeypatch, tmp_path):
    isolate_source_files(monkeypatch, tmp_path)
    secrets = {
        "FRED_API_KEY": "secret-fred-value",
        "OPENAI_API_KEY": "secret-openai-value",
        "ANTHROPIC_API_KEY": "secret-anthropic-value",
        "GOOGLE_API_KEY": "secret-google-value",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("HCP_USE_REAL_LLM", "false")

    audit = audit_sources(test_connections=False)
    rendered = str(audit)

    for value in secrets.values():
        assert value not in rendered


def test_openai_configured_is_connected_by_default(monkeypatch, tmp_path):
    isolate_source_files(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-openai-value")
    monkeypatch.delenv("HCP_USE_REAL_LLM", raising=False)
    monkeypatch.setattr(OpenAIClient, "is_available", lambda self: True)

    audit = audit_sources(test_connections=False)
    openai = record_named(audit, "OpenAI")

    assert openai["mode"] == "Connected"
    assert openai["reachable"] is True
    assert "secret-openai-value" not in str(openai)


def test_source_audit_unreachable_source_returns_structured_status(monkeypatch, tmp_path):
    isolate_source_files(monkeypatch, tmp_path)
    monkeypatch.setenv("FRED_API_KEY", "secret-fred-value")

    def fake_health_status(self):
        return {
            "source": "FRED",
            "configured": True,
            "reachable": False,
            "latest_successful_pull": None,
            "mode": "fallback",
            "message": "Fallback Mode - FRED unavailable: HTTP 400 from FRED",
        }

    monkeypatch.setattr(FREDConnector, "health_status", fake_health_status)

    fred = run_source_test("FRED")

    assert fred["mode"] == "Fallback"
    assert fred["reachable"] is False
    assert fred["latest_error"] == "Fallback Mode - FRED unavailable: HTTP 400 from FRED"
    assert "secret-fred-value" not in str(fred)


def test_valid_mocked_response_marks_fred_connected(monkeypatch, tmp_path):
    isolate_source_files(monkeypatch, tmp_path)
    monkeypatch.setenv("FRED_API_KEY", "secret-fred-value")

    def fake_health_status(self):
        return {
            "source": "FRED",
            "configured": True,
            "reachable": True,
            "latest_successful_pull": "2026-08-06T13:21:25.863803",
            "mode": "live",
            "message": "Live Data Mode - FRED connected",
        }

    monkeypatch.setattr(FREDConnector, "health_status", fake_health_status)
    fred = record_named(audit_sources(test_connections=False), "FRED")

    assert fred["mode"] == "Connected"
    assert fred["configured"] is True
    assert fred["reachable"] is True
    assert fred["last_success"] == "2026-08-06T13:21:25.863803"


def test_comparison_readiness_requires_more_than_fred():
    names = [
        "FRED",
        "BLS",
        "BEA",
        "Census Bureau",
        "Yahoo Finance",
        "SEC EDGAR",
        "World Bank",
        "IMF",
        "OpenAI",
        "Anthropic",
        "Gemini / Google",
    ]
    records = [{"source_name": name, "mode": "Connected" if name == "FRED" else "Key Needed"} for name in names]

    readiness = scenario_comparison_readiness(records)

    assert readiness["macro_data_readiness"] == "Partially Live"
    assert readiness["overall_status"] != "Ready for Research Comparison"
    assert "TradingEconomics is intentionally excluded" in readiness["note"]


def test_comparison_readiness_ready_without_trading_economics():
    names = [
        "FRED",
        "BLS",
        "BEA",
        "Census Bureau",
        "Yahoo Finance",
        "SEC EDGAR",
        "World Bank",
        "IMF",
        "OpenAI",
        "TradingEconomics",
    ]
    records = [
        {"source_name": name, "mode": "Unavailable" if name == "TradingEconomics" else "Connected"}
        for name in names
    ]

    readiness = scenario_comparison_readiness(records)

    assert readiness["overall_status"] == "Ready for Research Comparison"
