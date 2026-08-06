from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.connectors.base import RAW_ROOT
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
from app.services.agent_llm import openai_status_probe
from app.services.llm import AnthropicClient, GeminiClient, OpenAIClient, real_llm_enabled


@dataclass(frozen=True)
class SourceSpec:
    source_name: str
    category: str
    connector_class: type | None
    required_environment_variables: tuple[str, ...]
    data_currently_retrieved: str
    rate_limit_or_licensing: str
    action_needed_when_missing: str
    stable_endpoint: bool = True
    required_for_research_readiness: bool = True
    opted_out: bool = False


SOURCE_SPECS: list[SourceSpec] = [
    SourceSpec("FRED", "Macro Data", FREDConnector, ("FRED_API_KEY",), "CPIAUCSL, PCEPI, UNRATE, FEDFUNDS, DGS10, T10Y2Y", "FRED API terms and key-based request limits apply.", "Add FRED_API_KEY to local .env."),
    SourceSpec("BLS", "Macro Data", BLSConnector, ("BLS_API_KEY",), "CPI, PPI final demand, and nonfarm payrolls.", "BLS API key-based request limits apply.", "Add BLS_API_KEY to local .env."),
    SourceSpec("BEA", "Macro Data", BEAConnector, ("BEA_API_KEY",), "NIPA real GDP and personal income table data.", "BEA API key-based request limits apply.", "Add BEA_API_KEY to local .env."),
    SourceSpec("Census Bureau", "Macro Data", CensusConnector, ("CENSUS_API_KEY",), "Retail sales, housing starts, and building permits from EITS datasets.", "Census API key required for current EITS access.", "Add CENSUS_API_KEY to local .env."),
    SourceSpec("Yahoo Finance", "Market Data", YahooFinanceConnector, tuple(), "SPY, GLD, TLT, and BTC-USD market proxies via yfinance with chart API fallback.", "Unofficial/free market data; review licensing before production use.", "No key needed; verify endpoint availability."),
    SourceSpec("SEC EDGAR", "Company / Filings", SECEdgarConnector, ("SEC_USER_AGENT",), "Recent large-cap filing activity via submissions endpoint.", "SEC requires descriptive User-Agent and fair access behavior.", "Set SEC_USER_AGENT with compliant contact string."),
    SourceSpec("World Bank", "International Macro", WorldBankConnector, tuple(), "World real GDP growth indicator.", "Open API; observe published limits.", "No key needed; verify endpoint availability."),
    SourceSpec("IMF", "International Macro", IMFConnector, tuple(), "IMF real GDP growth data mapper indicator.", "Open endpoint; endpoint format can change.", "No key needed; verify endpoint availability."),
    SourceSpec("TradingEconomics", "Macro Calendar", TradingEconomicsConnector, tuple(), "Not used by current configuration; paid subscription source intentionally excluded.", "Credentials and paid plan/licensing required.", "No action required unless you later choose to license TradingEconomics.", stable_endpoint=False, required_for_research_readiness=False, opted_out=True),
    SourceSpec("CME FedWatch", "Rates / Policy", CMEFedWatchConnector, tuple(), "No stable unauthenticated JSON endpoint; returns unavailable placeholder.", "Use licensed/approved CME data before production.", "Provide approved CME endpoint or licensed feed.", stable_endpoint=False, required_for_research_readiness=False),
    SourceSpec("OpenAI", "Model Provider", None, ("OPENAI_API_KEY",), "Chat completion slot for model debate when real LLM mode is enabled.", "Provider API pricing and data policies apply.", "Add OPENAI_API_KEY and set HCP_USE_REAL_LLM=true."),
    SourceSpec("Anthropic", "Model Provider", None, ("ANTHROPIC_API_KEY",), "Optional Claude provider slot for model debate.", "Provider API pricing and data policies apply.", "Optional: add ANTHROPIC_API_KEY for provider diversity.", required_for_research_readiness=False),
    SourceSpec("Gemini / Google", "Model Provider", None, ("GOOGLE_API_KEY",), "Optional Gemini provider slot for model debate.", "Provider API pricing and data policies apply.", "Optional: add GOOGLE_API_KEY for provider diversity.", required_for_research_readiness=False),
]


def audit_sources(test_connections: bool = False) -> dict[str, Any]:
    records = [_source_record(spec, test_connections=test_connections) for spec in SOURCE_SPECS]
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "records": records,
        "groups": _group_records(records),
        "comparison_readiness": scenario_comparison_readiness(records),
    }


def test_source(source_name: str) -> dict[str, Any]:
    target = next((spec for spec in SOURCE_SPECS if spec.source_name.lower() == source_name.lower()), None)
    if not target:
        return {"source_name": source_name, "mode": "Error", "latest_error": "unknown source"}
    return _source_record(target, test_connections=True)


def scenario_comparison_readiness(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {row["source_name"]: row for row in records}

    def live(name: str) -> bool:
        return by_name.get(name, {}).get("mode") == "Connected"

    macro_sources = ["FRED", "BLS", "BEA", "Census Bureau"]
    international = ["World Bank", "IMF"]
    model_sources = ["OpenAI"]
    readiness = {
        "macro_data_readiness": _readiness_label(sum(live(name) for name in macro_sources), len(macro_sources)),
        "market_price_readiness": "Ready" if live("Yahoo Finance") else "Demo/Fallback",
        "international_data_readiness": _readiness_label(sum(live(name) for name in international), len(international)),
        "company_filing_readiness": "Ready" if live("SEC EDGAR") else "Needs SEC_USER_AGENT or endpoint test",
        "model_debate_readiness": _readiness_label(sum(live(name) for name in model_sources), len(model_sources)),
        "historical_analog_readiness": "Ready" if RAW_ROOT.exists() else "Demo library only",
    }
    strong_count = sum(value in {"Ready", "Mostly Ready"} for value in readiness.values())
    if strong_count >= 5 and readiness["macro_data_readiness"] in {"Ready", "Mostly Ready"} and readiness["model_debate_readiness"] == "Ready":
        overall = "Ready for Research Comparison"
    elif strong_count >= 2 or readiness["macro_data_readiness"] in {"Partially Live", "Mostly Ready"}:
        overall = "Partially Live"
    else:
        overall = "Demo Only"
    readiness["overall_status"] = overall
    readiness["note"] = "TradingEconomics is intentionally excluded. Readiness is based on FRED, BLS, BEA, Census, Yahoo Finance, SEC EDGAR, World Bank, IMF, and OpenAI."
    return readiness


def _source_record(spec: SourceSpec, test_connections: bool) -> dict[str, Any]:
    configured = _configured(spec.required_environment_variables)
    connector_present = spec.connector_class is not None or spec.category == "Model Provider"
    latest_success = _latest_success(spec.source_name)
    reachable = bool(latest_success)
    latest_error = None
    mode = _initial_mode(spec, configured, reachable)
    if spec.opted_out:
        mode = "Unavailable"
        reachable = False
        latest_error = "source intentionally excluded from current configuration"
    elif spec.source_name == "FRED":
        status = FREDConnector().health_status()
        reachable = bool(status.get("reachable"))
        latest_success = status.get("latest_successful_pull") or latest_success
        mode = "Connected" if status.get("mode") == "live" and reachable else "Fallback" if configured else "Key Needed"
        latest_error = None if reachable else status.get("message")
    elif spec.category == "Model Provider":
        if test_connections and spec.source_name == "OpenAI":
            probe = openai_status_probe()
            reachable = bool(probe.get("reachable"))
            mode = probe.get("mode", "Fallback")
            latest_error = probe.get("latest_error")
        else:
            reachable = _model_available(spec.source_name)
            mode = "Connected" if reachable else "Key Needed" if not configured else "Fallback"
            latest_error = None if reachable else ("HCP_USE_REAL_LLM=false" if configured and not real_llm_enabled() else None)
    elif test_connections and connector_present:
        mode, reachable, latest_success, latest_error = _test_connector(spec, configured, latest_success)
    action = _action_needed(spec, configured, reachable, mode)
    return {
        "source_name": spec.source_name,
        "category": spec.category,
        "connector_present": connector_present,
        "configured": configured,
        "reachable": reachable,
        "mode": mode,
        "last_success": latest_success,
        "latest_error": _safe_text(latest_error),
        "required_environment_variables": list(spec.required_environment_variables),
        "action_needed": action,
        "data_currently_retrieved": spec.data_currently_retrieved,
        "rate_limit_or_licensing": spec.rate_limit_or_licensing,
        "required_for_research_readiness": spec.required_for_research_readiness,
    }


def _test_connector(spec: SourceSpec, configured: bool, latest_success: str | None) -> tuple[str, bool, str | None, str | None]:
    if not spec.stable_endpoint:
        return "Unavailable", False, latest_success, "No stable unauthenticated endpoint configured"
    if spec.required_environment_variables and not configured:
        return "Key Needed", False, latest_success, "required credential missing"
    previous_real_data = os.environ.get("HCP_USE_REAL_DATA")
    os.environ["HCP_USE_REAL_DATA"] = "true"
    try:
        connector = spec.connector_class()
        signals = connector.fetch_signals()
        live = any(signal.value != "unavailable" for signal in signals)
        latest = _latest_success(spec.source_name) or latest_success
        return ("Connected" if live else "Fallback"), live, latest, None if live else signals[0].interpretation if signals else "no signals"
    except Exception as exc:
        return "Error", False, latest_success, exc.__class__.__name__
    finally:
        if previous_real_data is None:
            os.environ.pop("HCP_USE_REAL_DATA", None)
        else:
            os.environ["HCP_USE_REAL_DATA"] = previous_real_data


def _configured(env_vars: tuple[str, ...]) -> bool:
    if not env_vars:
        return True
    return all(bool(os.getenv(name)) for name in env_vars)


def _model_available(source_name: str) -> bool:
    clients = {"OpenAI": OpenAIClient(), "Anthropic": AnthropicClient(), "Gemini / Google": GeminiClient()}
    return clients[source_name].is_available()


def _initial_mode(spec: SourceSpec, configured: bool, reachable: bool) -> str:
    if not spec.connector_class and spec.category != "Model Provider":
        return "Unavailable"
    if reachable:
        return "Connected"
    if not spec.stable_endpoint:
        return "Unavailable"
    if spec.required_environment_variables and not configured:
        return "Key Needed"
    return "Untested"


def _action_needed(spec: SourceSpec, configured: bool, reachable: bool, mode: str) -> str:
    if mode == "Connected" and reachable:
        return "None."
    if mode == "Unavailable":
        return spec.action_needed_when_missing
    if spec.required_environment_variables and not configured:
        return spec.action_needed_when_missing
    if spec.category == "Model Provider" and configured and not real_llm_enabled():
        return "Set HCP_USE_REAL_LLM=true when ready to use live provider calls."
    return "Run Test Connection and review endpoint response."


def _latest_success(source_name: str) -> str | None:
    source_dir = RAW_ROOT / _safe_source(source_name)
    if not source_dir.exists():
        return None
    recent_paths = sorted(source_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:200]
    for path in recent_paths:
        try:
            with path.open(errors="ignore") as handle:
                header = handle.read(4096)
        except OSError:
            continue
        if '"unavailable": true' not in header:
            return datetime.utcfromtimestamp(path.stat().st_mtime).isoformat()
    return None


def _safe_source(source_name: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in source_name).strip("_")


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    for env_var in {name for spec in SOURCE_SPECS for name in spec.required_environment_variables}:
        secret = os.getenv(env_var)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def _group_records(records: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups = {
        "implemented_and_live": [],
        "implemented_needing_credentials": [],
        "implemented_but_untested": [],
        "unavailable_no_stable_endpoint": [],
        "not_yet_implemented": [],
    }
    for row in records:
        if not row["connector_present"] and row["category"] != "Model Provider":
            groups["not_yet_implemented"].append(row["source_name"])
        elif row["mode"] == "Connected":
            groups["implemented_and_live"].append(row["source_name"])
        elif row["mode"] == "Key Needed":
            groups["implemented_needing_credentials"].append(row["source_name"])
        elif row["mode"] == "Unavailable":
            groups["unavailable_no_stable_endpoint"].append(row["source_name"])
        else:
            groups["implemented_but_untested"].append(row["source_name"])
    return groups


def _readiness_label(live_count: int, total: int) -> str:
    if live_count == total:
        return "Ready"
    if live_count > 0:
        return "Mostly Ready" if live_count / total >= 0.5 else "Partially Live"
    return "Demo/Fallback"
