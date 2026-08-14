import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st

from scenario_state import apply_successful_parse, normalize_scenario_options
from time_utils import format_dashboard_timestamp, format_relative_freshness


API_URL = os.getenv("HCP_API_URL", "http://localhost:8000")
ROOT = Path(__file__).resolve().parents[1]
TRAINING_DATASET = ROOT / "datasets" / "cleaned_examples" / "hcp_macro_training.jsonl"


def api_get(path: str, default: Any = None) -> Any:
    try:
        response = requests.get(f"{API_URL}{path}", timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.session_state.api_warnings.append(f"GET {path}: {exc}")
        return default


def api_post(path: str, payload: dict | None = None, default: Any = None, timeout: float = 90) -> Any:
    try:
        response = requests.post(f"{API_URL}{path}", json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.session_state.api_warnings.append(f"POST {path}: {exc}")
        return default


def api_get_bytes(path: str) -> bytes | None:
    try:
        response = requests.get(f"{API_URL}{path}", timeout=90)
        response.raise_for_status()
        return response.content
    except requests.RequestException as exc:
        st.session_state.api_warnings.append(f"GET {path}: {exc}")
        return None


def run_local_command(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=180)
    return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def refresh_artifacts() -> None:
    st.session_state.signals = api_get("/signals", {"signals": [], "source_status": {}})
    st.session_state.fred_health = api_get("/health/fred", {})
    st.session_state.source_audit = api_get("/system/source-status", {"records": [], "comparison_readiness": {}})
    st.session_state.reports = api_get("/history/reports", [])
    st.session_state.thesis_history = api_get("/history/thesis", [])
    st.session_state.debates = api_get("/history/debates", [])
    st.session_state.approvals = api_get("/approvals", [])
    st.session_state.outcomes = api_get("/outcomes", {})
    st.session_state.conviction_ranking_eval = api_get("/outcomes/conviction-ranking-evaluation", {})
    st.session_state.proxy_mappings = api_get("/outcomes/proxy-mappings", [])
    st.session_state.scheduler_status = api_get("/system/scheduler", {})
    st.session_state.latest_calibration = api_get("/outcomes/latest-calibration-report", None)
    st.session_state.readiness = api_get("/training/fine-tuning-readiness", {})
    st.session_state.institutional_readiness = api_get("/institutional/readiness", {})
    st.session_state.institutional_documents = api_get("/institutional/documents", [])
    st.session_state.historical_postmortems = api_get("/institutional/postmortems", [])
    st.session_state.ic_reports = api_get("/investment-committee/reports", [])
    st.session_state.scenario_lab = api_get("/scenario-lab", {})
    previous_options = st.session_state.get("scenario_options", {})
    raw_scenario_options = api_get("/scenario-lab/options", None)
    scenario_options, scenario_options_debug = normalize_scenario_options(raw_scenario_options, previous_options)
    st.session_state.scenario_options_api_response = raw_scenario_options
    st.session_state.scenario_options = scenario_options
    st.session_state.scenario_options_debug = scenario_options_debug
    st.session_state.scenario_parser_health = api_get("/scenario-lab/parser-health", {})
    st.session_state.regimes = api_get("/regimes", [])
    st.session_state.backtests = api_get("/backtests/historical", [])
    st.session_state.lessons = api_get("/memory/lessons", {})


def load_training_dataset_preview(limit: int = 5) -> dict[str, Any]:
    if not TRAINING_DATASET.exists():
        return {"count": 0, "latest": [], "path": str(TRAINING_DATASET)}
    rows = [json.loads(line) for line in TRAINING_DATASET.read_text().splitlines() if line.strip()]
    return {"count": len(rows), "latest": rows[-limit:], "path": str(TRAINING_DATASET)}


def data_mode_from_state() -> str:
    outlook = st.session_state.get("scenario_outlook") or {}
    if outlook.get("data_mode"):
        return outlook["data_mode"].replace("Live Data Mode - FRED connected", "Live Data Mode — FRED connected")
    fred = st.session_state.get("fred_health") or {}
    if fred.get("configured") and fred.get("reachable") and fred.get("mode") == "live":
        return "Live Data Mode — FRED connected"
    statuses = (st.session_state.get("signals") or {}).get("source_status", {})
    if "connected" in str(statuses.get("FRED", "")).lower():
        return "Live Data Mode — FRED connected"
    if statuses and all("ok" in str(value).lower() for value in statuses.values()):
        return "Live Data Mode"
    return "Demo Mode: Some outputs are based on fallback data and should not be treated as live investment research."


def table(rows: list[dict[str, Any]], columns: list[str] | None = None, empty: str = "No records available yet.") -> None:
    if not rows:
        st.info(empty)
        return
    frame = pd.DataFrame(rows)
    if columns:
        existing = [column for column in columns if column in frame.columns]
        frame = frame[existing]
    st.dataframe(frame, use_container_width=True, hide_index=True)


def format_timestamp_columns(rows: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    formatted = []
    for row in rows:
        item = dict(row)
        for field in fields:
            if field in item:
                item[field] = format_dashboard_timestamp(item.get(field))
        formatted.append(item)
    return formatted


def dashboard_table(rows: list[dict[str, Any]], columns: list[str] | None = None, empty: str = "No records available yet.") -> None:
    table(format_timestamp_columns(rows, ["created_at", "updated_at", "approved_at", "rejected_at"]), columns, empty)


def source_status_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        mode = record.get("mode")
        rows.append(
            {
                "Source": record.get("source_name"),
                "Category": record.get("category"),
                "Connector": "Yes" if record.get("connector_present") else "No",
                "Configured": "Yes" if record.get("configured") else "No",
                "Reachable": "Yes" if record.get("reachable") else "No",
                "Mode": status_badge(mode),
                "Last Successful Pull": format_dashboard_timestamp(record.get("last_success")),
                "Action Needed": record.get("action_needed"),
            }
        )
    return rows


def status_badge(mode: str | None) -> str:
    mapping = {
        "Connected": "✓ Connected",
        "Fallback": "⚠ Fallback",
        "Error": "✗ Error",
        "Untested": "○ Untested",
        "Key Needed": "⚠ Key Needed",
        "Unavailable": "✗ Unavailable",
    }
    return mapping.get(str(mode), f"○ {mode or 'Untested'}")


def render_outlook(outlook: dict[str, Any]) -> None:
    if not outlook or outlook.get("status") != "ok":
        st.info("Enter a scenario and click Generate HCP Outlook to create the investment committee briefing.")
        for warning in outlook.get("warnings", []) if isinstance(outlook, dict) else []:
            st.warning(warning)
        return

    if outlook.get("demo"):
        st.info("Demo scenario: Inflation Surprise Cycle - Phase 1.")
    if outlook["data_mode"].startswith("Demo Mode"):
        st.warning(outlook["data_mode"])
    else:
        st.success(outlook["data_mode"])

    st.subheader("Executive Outlook")
    st.write(outlook["executive_outlook"])

    case_cols = st.columns(3)
    with case_cols[0]:
        st.markdown("**Base Case**")
        st.metric("Probability", f"{outlook['base_case']['probability']:.0%}")
        st.write(outlook["base_case"]["growth_path"])
        st.write(outlook["base_case"]["inflation_path"])
        st.write(outlook["base_case"]["central_bank_response"])
        st.write(outlook["base_case"]["market_consequence"])
    with case_cols[1]:
        st.markdown("**Bull Case**")
        st.metric("Probability", f"{outlook['bull_case']['probability']:.0%}")
        st.write(f"Trigger: {outlook['bull_case']['key_trigger']}")
        st.write("Likely winners: " + ", ".join(outlook["bull_case"]["likely_winners"]))
    with case_cols[2]:
        st.markdown("**Bear / Tail Case**")
        st.metric("Probability", f"{outlook['bear_tail_case']['probability']:.0%}")
        st.write(f"Trigger: {outlook['bear_tail_case']['key_trigger']}")
        st.write("Likely losers: " + ", ".join(outlook["bear_tail_case"]["likely_losers"]))
        st.write(outlook["bear_tail_case"]["defensive_response"])

    st.subheader("Expected Asset-Class Performance")
    table(
        outlook.get("expected_asset_class_performance", []),
        ["asset_class", "subsegment", "outlook", "conviction", "primary_macro_driver", "major_risk", "relevant_horizon"],
    )

    st.subheader("Suggested Portfolio")
    st.markdown("**Long / Overweight**")
    table(
        outlook.get("suggested_portfolio", {}).get("long_overweight", []),
        ["asset_class", "subsegment", "direction", "conviction", "expected_holding_horizon", "why_now", "main_risk", "tracking_benchmark_proxy"],
    )
    st.markdown("**Short / Underweight**")
    table(
        outlook.get("suggested_portfolio", {}).get("short_underweight", []),
        ["asset_class", "subsegment", "direction", "conviction", "expected_holding_horizon", "why_now", "main_risk", "tracking_benchmark_proxy"],
    )
    st.caption("Tracking proxies measure paper outcomes only. Recommendations are asset-class/subsegment views, not security trades.")

    st.subheader("What Would Change the View")
    left, right = st.columns(2)
    with left:
        st.markdown("**Confirming Indicators**")
        for item in outlook["what_would_change_the_view"]["confirming_indicators"]:
            st.markdown(f"- {item}")
    with right:
        st.markdown("**Invalidating Indicators**")
        for item in outlook["what_would_change_the_view"]["invalidating_indicators"]:
            st.markdown(f"- {item}")

    st.subheader("Data to Watch Next")
    for item in outlook["data_to_watch_next"]:
        st.markdown(f"- {item}")


def latest_report() -> dict[str, Any] | None:
    reports = st.session_state.get("ic_reports", [])
    return reports[0] if reports else None


def default_scenario() -> dict[str, Any]:
    return {
        "scenario_name": "Neutral Scenario",
        "scenario_description": "",
        "growth_outlook": "moderate growth",
        "growth_surprise": "in line",
        "inflation_direction": "stable inflation",
        "inflation_surprise": "in line",
        "recession_probability": 0.3,
        "market_volatility": "normal",
        "central_bank_stance": "neutral",
        "fed_position": "roughly on time",
        "expected_fed_response": "hold",
        "labor_market": "cooling",
        "financial_conditions": "neutral",
        "credit_stress": 3,
        "dollar_outlook": "stable",
        "commodity_shock": "none",
        "equity_valuation": "fair",
        "market_sentiment": "neutral",
        "margin_debt": "moderate",
        "time_horizon": "3-6 months",
        "probability": None,
        "countries_or_regions": ["U.S."],
        "custom_assumptions": "",
        "risks": [],
        "invalidation_triggers": [],
        "parser_provider": "manual",
        "parser_model": None,
        "scenario_id": None,
        "scenario_hash": None,
    }


def _bump_scenario_widget_version() -> None:
    st.session_state.scenario_widget_version = int(st.session_state.get("scenario_widget_version", 0)) + 1


def set_current_scenario(scenario: dict[str, Any], *, status: str, widgets_refreshed: bool = True) -> None:
    current = dict(scenario)
    current["widgets_refreshed"] = widgets_refreshed
    st.session_state.current_scenario = current
    st.session_state.scenario_builder = current
    st.session_state.scenario_parse_status = status
    st.session_state.scenario_assumptions_confirmed = False
    st.session_state.scenario_parse_pending = True
    st.session_state.scenario_outlook = {}
    st.session_state.active_preset = None
    _bump_scenario_widget_version()


def reset_scenario_state(clear_text: bool = True) -> None:
    if clear_text:
        st.session_state.plain_english_scenario_text = ""
    st.session_state.active_preset = None
    st.session_state.scenario_parse_status = "Reset to neutral defaults."
    st.session_state.scenario_parse_timing = {}
    st.session_state.scenario_assumptions_confirmed = False
    st.session_state.scenario_parse_pending = False
    st.session_state.scenario_outlook = {}
    set_current_scenario(default_scenario(), status="Reset scenario loaded.", widgets_refreshed=True)
    st.session_state.scenario_parse_pending = False


def option_index(options: list[str], value: Any) -> int:
    return options.index(value) if value in options else 0


def _duration_label(value: Any) -> str:
    if value in {None, ""}:
        return "not available"
    try:
        duration = int(float(value))
    except (TypeError, ValueError):
        return "not available"
    if duration < 1000:
        return f"{duration} ms"
    return f"{duration / 1000:.1f} sec"


def merge_builder_updates(builder: dict[str, Any]) -> dict[str, Any]:
    prior_debug = st.session_state.get("scenario_options_debug", {})
    options, options_debug = normalize_scenario_options(st.session_state.get("scenario_options"))
    st.session_state.scenario_options = options
    st.session_state.scenario_options_debug = {
        **options_debug,
        "api_response": st.session_state.get("scenario_options_api_response"),
        "api_missing_fields": prior_debug.get("api_missing_fields", options_debug["api_missing_fields"]),
        "fallback_fields": prior_debug.get("fallback_fields", options_debug["fallback_fields"]),
    }
    key_suffix = st.session_state.get("scenario_widget_version", 0)
    region_options = options.get("countries_or_regions", [])
    existing_regions = builder.get("countries_or_regions", ["U.S."])
    selected_regions = [region for region in existing_regions if region in region_options]
    custom_regions = ", ".join(region for region in existing_regions if region not in region_options)
    with st.form("structured_scenario_editor"):
        st.subheader("Structured Scenario Summary")
        provider = builder.get("parser_provider") or "not specified"
        model = builder.get("parser_model") or "not specified"
        scenario_id = builder.get("scenario_id") or "not assigned"
        scenario_hash = builder.get("scenario_hash") or "not assigned"
        meta_cols = st.columns(4)
        meta_cols[0].caption("Parser Provider")
        meta_cols[0].code(str(provider), language=None)
        meta_cols[1].caption("Parser Model")
        meta_cols[1].code(str(model), language=None)
        meta_cols[2].caption("Scenario ID")
        meta_cols[2].code(str(scenario_id), language=None)
        meta_cols[3].caption("Scenario Hash")
        meta_cols[3].code(str(scenario_hash), language=None)
        status_cols = st.columns(3)
        status_cols[0].caption("Parse Status")
        status_cols[0].write(st.session_state.get("scenario_parse_status", "Not parsed yet."))
        status_cols[1].caption("Parse Duration")
        status_cols[1].write(_duration_label(builder.get("parse_duration_ms")))
        status_cols[2].caption("Widget Values Refreshed")
        status_cols[2].write("Yes" if builder.get("widgets_refreshed") else "Not yet")
        timings = builder.get("parse_timing") or st.session_state.get("scenario_parse_timing") or {}
        if timings:
            st.caption(
                "Parser timing: "
                + " | ".join(f"{key.replace('_', ' ')}: {_duration_label(value)}" for key, value in timings.items())
            )
        st.markdown("**Section A - Macro Conditions**")
        c1, c2 = st.columns(2)
        scenario_name = c1.text_input("Scenario name", value=builder.get("scenario_name", "Custom Macro Scenario"), key=f"scenario_name_{key_suffix}")
        scenario_description = c2.text_area("Scenario description", value=builder.get("scenario_description", ""), height=90, key=f"scenario_description_{key_suffix}")
        c1, c2, c3 = st.columns(3)
        growth = c1.selectbox("Growth", options.get("growth_outlook", []), index=option_index(options.get("growth_outlook", []), builder.get("growth_outlook")), key=f"growth_{key_suffix}")
        growth_surprise = c2.selectbox("Growth surprise", options.get("growth_surprise", []), index=option_index(options.get("growth_surprise", []), builder.get("growth_surprise")), key=f"growth_surprise_{key_suffix}")
        inflation = c3.selectbox("Inflation", options.get("inflation_direction", []), index=option_index(options.get("inflation_direction", []), builder.get("inflation_direction")), key=f"inflation_{key_suffix}")
        c1, c2, c3 = st.columns(3)
        inflation_surprise = c1.selectbox("Inflation surprise", options.get("inflation_surprise", []), index=option_index(options.get("inflation_surprise", []), builder.get("inflation_surprise")), key=f"inflation_surprise_{key_suffix}")
        fed_stance = c2.selectbox("Current Fed stance", options.get("central_bank_stance", []), index=option_index(options.get("central_bank_stance", []), builder.get("central_bank_stance")), key=f"fed_stance_{key_suffix}")
        fed_position = c3.selectbox("Fed position", options.get("fed_position", []), index=option_index(options.get("fed_position", []), builder.get("fed_position")), key=f"fed_position_{key_suffix}")
        c1, c2, c3 = st.columns(3)
        expected_fed_response = c1.selectbox("Expected Fed response", options.get("expected_fed_response", []), index=option_index(options.get("expected_fed_response", []), builder.get("expected_fed_response")), key=f"expected_fed_response_{key_suffix}")
        labor = c2.selectbox("Labor market", options.get("labor_market", []), index=option_index(options.get("labor_market", []), builder.get("labor_market")), key=f"labor_{key_suffix}")
        financial = c3.selectbox("Financial conditions", options.get("financial_conditions", []), index=option_index(options.get("financial_conditions", []), builder.get("financial_conditions")), key=f"financial_{key_suffix}")
        c1, c2, c3 = st.columns(3)
        volatility = c1.selectbox("Market volatility", options.get("market_volatility", []), index=option_index(options.get("market_volatility", []), builder.get("market_volatility")), key=f"volatility_{key_suffix}")
        dollar = c2.selectbox("Dollar outlook", options.get("dollar_outlook", []), index=option_index(options.get("dollar_outlook", []), builder.get("dollar_outlook")), key=f"dollar_{key_suffix}")
        commodity = c3.selectbox("Commodity shock", options.get("commodity_shock", []), index=option_index(options.get("commodity_shock", []), builder.get("commodity_shock")), key=f"commodity_{key_suffix}")
        c1, c2, c3 = st.columns(3)
        valuation = c1.selectbox("Equity valuation", options.get("equity_valuation", []), index=option_index(options.get("equity_valuation", []), builder.get("equity_valuation")), key=f"valuation_{key_suffix}")
        market_sentiment = c2.selectbox("Market sentiment", options.get("market_sentiment", []), index=option_index(options.get("market_sentiment", []), builder.get("market_sentiment")), key=f"market_sentiment_{key_suffix}")
        margin_debt = c3.selectbox("Margin debt", options.get("margin_debt", []), index=option_index(options.get("margin_debt", []), builder.get("margin_debt")), key=f"margin_debt_{key_suffix}")
        c1, c2 = st.columns(2)
        horizon = c1.selectbox("Time horizon", options.get("time_horizon", []), index=option_index(options.get("time_horizon", []), builder.get("time_horizon")), key=f"horizon_{key_suffix}")
        st.markdown("**Section B - Risk and Probability**")
        c1, c2, c3 = st.columns(3)
        credit_stress = c1.slider("Credit stress", 0, 10, int(builder.get("credit_stress", 3)), key=f"credit_stress_{key_suffix}")
        c1.caption(f"{credit_stress} / 10")
        recession_pct = c2.slider("Recession probability", 0, 100, int(round(float(builder.get("recession_probability", 0.3)) * 100)), 1, key=f"recession_{key_suffix}")
        c2.caption(f"{recession_pct}%")
        probability_value = builder.get("probability")
        probability_pct = c3.slider("Scenario probability", 0, 100, int(round(float(probability_value) * 100)) if probability_value is not None else 50, 1, key=f"probability_{key_suffix}")
        c3.caption(f"{probability_pct}%")
        probability_specified = c3.checkbox("Scenario probability specified", value=probability_value is not None, key=f"probability_specified_{key_suffix}")
        st.markdown("**Section C - Regions and Narrative**")
        c1, c2 = st.columns(2)
        countries = c1.multiselect("Countries/regions", region_options, default=selected_regions, key=f"countries_{key_suffix}")
        custom_countries = c2.text_input("Custom regions", value=custom_regions, key=f"custom_countries_{key_suffix}")
        custom_assumptions = st.text_area("Custom assumptions", value=builder.get("custom_assumptions", ""), height=90, key=f"custom_assumptions_{key_suffix}")
        risks = st.text_area("Risks", value="\n".join(builder.get("risks", [])), height=90, key=f"risks_{key_suffix}")
        invalidation = st.text_area("Invalidation triggers", value="\n".join(builder.get("invalidation_triggers", [])), height=90, key=f"invalidation_{key_suffix}")
        c1, c2 = st.columns([1, 1])
        save_summary = c1.form_submit_button("Update Scenario Summary", use_container_width=True)
        generate = c2.form_submit_button("Generate HCP Outlook", type="primary", use_container_width=True)
    regions = countries + [item.strip() for item in custom_countries.split(",") if item.strip()]
    updated = {
        "scenario_name": scenario_name,
        "scenario_description": scenario_description,
        "growth_outlook": growth,
        "growth_surprise": growth_surprise,
        "inflation_direction": inflation,
        "inflation_surprise": inflation_surprise,
        "central_bank_stance": fed_stance,
        "fed_position": fed_position,
        "expected_fed_response": expected_fed_response,
        "labor_market": labor,
        "financial_conditions": financial,
        "market_volatility": volatility,
        "credit_stress": credit_stress,
        "dollar_outlook": dollar,
        "commodity_shock": commodity,
        "equity_valuation": valuation,
        "market_sentiment": market_sentiment,
        "margin_debt": margin_debt,
        "time_horizon": horizon,
        "recession_probability": recession_pct / 100,
        "probability": probability_pct / 100 if probability_specified else None,
        "countries_or_regions": regions,
        "custom_assumptions": custom_assumptions,
        "risks": [item.strip() for item in risks.splitlines() if item.strip()],
        "invalidation_triggers": [item.strip() for item in invalidation.splitlines() if item.strip()],
        "parser_provider": builder.get("parser_provider"),
        "parser_model": builder.get("parser_model"),
        "scenario_id": builder.get("scenario_id"),
        "scenario_hash": builder.get("scenario_hash"),
        "confirmed_scenario_id": builder.get("confirmed_scenario_id"),
        "confirmed_scenario_hash": builder.get("confirmed_scenario_hash"),
        "parser_confidence": builder.get("parser_confidence"),
        "field_confidence": builder.get("field_confidence"),
        "field_excerpts": builder.get("field_excerpts"),
        "low_confidence_fields": builder.get("low_confidence_fields", []),
        "parser_warnings": builder.get("parser_warnings", []),
        "source_text": builder.get("source_text"),
        "stated_probabilities": builder.get("stated_probabilities", {}),
        "phases": builder.get("phases", []),
        "parse_duration_ms": builder.get("parse_duration_ms"),
        "parse_timing": builder.get("parse_timing", {}),
        "widgets_refreshed": builder.get("widgets_refreshed", False),
    }
    return {"scenario": updated, "save_summary": save_summary, "generate": generate}


st.set_page_config(page_title="HCP Macro Theme AI", layout="wide")
st.session_state.setdefault("api_warnings", [])
st.session_state.api_warnings = []

if "loaded" not in st.session_state:
    refresh_artifacts()
    st.session_state.loaded = True

st.title("HCP Macro Theme AI Investment System")
st.write(
    "An AI-assisted macro research platform that turns scenario assumptions, market data, historical analogs, and HCP institutional memory into decision-useful research hypotheses for human review."
)
st.caption("Research hypotheses only. Human approval required. No trade execution.")

mode_label = data_mode_from_state()
if mode_label.startswith("Demo Mode"):
    st.warning(mode_label)
else:
    st.success(mode_label)

with st.sidebar:
    st.header("Demo Controls")
    if st.button("Refresh Dashboard", use_container_width=True):
        refresh_artifacts()
        st.rerun()
    if st.button("Load Demo Scenario", use_container_width=True):
        with st.status("Preparing HCP demo outlook", expanded=True) as status:
            st.write("Reading current data")
            st.write("Retrieving historical analogs")
            st.write("Running specialist agents")
            st.write("Running model debate")
            st.write("Building final outlook")
            st.session_state.scenario_outlook = api_post("/scenario-lab/demo-outlook", {}, {})
            refresh_artifacts()
            status.update(label="Demo outlook ready", state="complete")
    st.divider()
    st.caption("Advanced operations are in System Monitor / Technical Details.")

tabs = st.tabs(
    [
        "Scenario Lab",
        "Historical Analogs",
        "Expected Asset-Class Performance",
        "Suggested Portfolio",
        "Portfolio Evolution",
        "Investment Committee Report",
        "Outcomes & Evaluation",
        "Historical HCP Reports",
        "System Monitor",
    ]
)

with tabs[0]:
    st.header("Scenario Lab")
    st.write("Describe a macro scenario in plain English or build one with controls, then review the structured assumptions before generating an HCP outlook.")
    st.session_state.setdefault("scenario_widget_version", 0)
    st.session_state.setdefault("plain_english_scenario_text", "Inflation surprises higher, growth remains strong, and the Fed delays tightening.")
    st.session_state.setdefault("current_scenario", default_scenario())
    st.session_state.setdefault("scenario_builder", st.session_state.current_scenario)
    st.session_state.scenario_builder = st.session_state.current_scenario
    prior_debug = st.session_state.get("scenario_options_debug", {})
    options, options_debug = normalize_scenario_options(st.session_state.get("scenario_options"))
    st.session_state.scenario_options = options
    st.session_state.scenario_options_debug = {
        **options_debug,
        "api_response": st.session_state.get("scenario_options_api_response"),
        "api_missing_fields": prior_debug.get("api_missing_fields", options_debug["api_missing_fields"]),
        "fallback_fields": prior_debug.get("fallback_fields", options_debug["fallback_fields"]),
    }

    input_tabs = st.tabs(["Describe a Scenario", "Build a Scenario"])
    with input_tabs[0]:
        if st.button("Reset Scenario", use_container_width=True):
            reset_scenario_state()
            st.rerun()
        scenario_text = st.text_area(
            "Plain-English scenario",
            height=160,
            key="plain_english_scenario_text",
        )

        def _run_parse(force_rule_fallback: bool = False) -> None:
            st.session_state.active_preset = None
            st.session_state.scenario_assumptions_confirmed = False
            st.session_state.scenario_outlook = {}
            st.session_state.scenario_parse_status = "Parsing scenario..."
            started = time.perf_counter()
            parsed = api_post(
                "/scenario-lab/parse",
                {"text": scenario_text, "force_rule_fallback": force_rule_fallback},
                {},
                timeout=15,
            )
            ui_update_started = time.perf_counter()
            st.session_state.latest_parsed_response = parsed
            if isinstance(parsed, dict) and parsed.get("status") == "ok" and isinstance(parsed.get("scenario"), dict):
                scenario = dict(parsed["scenario"])
                timing = dict(scenario.get("parse_timing") or {})
                timing["ui_update_ms"] = int((time.perf_counter() - ui_update_started) * 1000)
                timing["streamlit_roundtrip_ms"] = int((time.perf_counter() - started) * 1000)
                scenario["parse_timing"] = timing
                scenario["widgets_refreshed"] = True
                parsed = {**parsed, "scenario": scenario}
                applied, apply_error = apply_successful_parse(st.session_state, parsed)
                if not applied:
                    st.session_state.scenario_parse_status = f"Parse response could not be applied: {apply_error}"
                    st.error(st.session_state.scenario_parse_status)
                    return
                st.success("Parsed scenario loaded into controls.")
            elif isinstance(parsed, dict) and parsed.get("status") == "not_ready":
                st.session_state.scenario_parse_status = "Parser unavailable; current scenario preserved."
                st.warning(f"Ollama parser unavailable: {parsed.get('warning')}")
                st.info("Choose Use Rule-Based Fallback, Enter Manually, or Retry Ollama.")
            else:
                st.session_state.scenario_parse_status = "Invalid parser response; current scenario preserved."
                st.error("Parser response could not be applied; the current scenario was preserved.")

        if st.button("Parse Scenario", use_container_width=True):
            with st.status("Parsing scenario", expanded=True) as status:
                st.write("Creating parser request")
                st.write("Running local Ollama inference")
                st.write("Validating JSON")
                st.write("Refreshing structured controls")
                _run_parse(False)
                status.update(label=st.session_state.get("scenario_parse_status", "Parse finished"), state="complete")
            st.rerun()
        cols = st.columns(2)
        if cols[0].button("Reparse Scenario", use_container_width=True):
            with st.status("Reparsing scenario", expanded=True) as status:
                st.write("Creating parser request")
                st.write("Running local Ollama inference")
                st.write("Validating JSON")
                st.write("Refreshing structured controls")
                _run_parse(False)
                status.update(label=st.session_state.get("scenario_parse_status", "Parse finished"), state="complete")
            st.rerun()
        if cols[1].button("Use Rule-Based Fallback", use_container_width=True):
            _run_parse(True)
            st.warning("Rule-based fallback parser used. Review required before analysis.")
            st.rerun()
        if st.button("Enter Manually", use_container_width=True):
            scenario = default_scenario()
            scenario["parser_provider"] = "manual"
            set_current_scenario(scenario, status="Manual structured controls loaded.", widgets_refreshed=True)
            st.info("Manual structured controls loaded. Review fields and click Use Parsed Values before analysis.")
            st.rerun()
        st.caption("Ollama is the primary parser. Rule-based parsing is available only as an explicit fallback.")

    with input_tabs[1]:
        st.markdown("**Scenario Presets**")
        preset_names = list(options.get("presets", {}).keys())
        for row_start in range(0, len(preset_names), 5):
            cols = st.columns(5)
            for col, name in zip(cols, preset_names[row_start:row_start + 5]):
                if col.button(name, key=f"preset_{name}", use_container_width=True):
                    preset = dict(options["presets"][name])
                    preset["parser_provider"] = "preset"
                    preset["parser_model"] = None
                    preset["scenario_id"] = None
                    preset["scenario_hash"] = None
                    set_current_scenario(preset, status=f"Loaded preset: {name}", widgets_refreshed=True)
                    st.session_state.scenario_parse_pending = False
                    st.session_state.scenario_assumptions_confirmed = False
                    st.session_state.active_preset = name
                    st.success(f"Loaded preset: {name}")
                    st.rerun()
        st.caption("Presets populate the controls, but all fields remain editable.")

    editor = merge_builder_updates(st.session_state.scenario_builder)
    st.session_state.current_scenario = editor["scenario"]
    st.session_state.scenario_builder = st.session_state.current_scenario
    summary = api_post("/scenario-lab/summary", {"scenario": st.session_state.current_scenario}, {"summary": {}})
    st.markdown("**Pre-Analysis Summary**")
    if st.session_state.scenario_builder.get("scenario_id"):
        st.caption(f"Scenario ID: {st.session_state.scenario_builder.get('scenario_id')} | Hash: {st.session_state.scenario_builder.get('scenario_hash')}")
    summary_rows = [{"assumption": key, "value": value} for key, value in summary.get("summary", {}).items()]
    table(summary_rows, ["assumption", "value"], "No scenario summary available yet.")
    parser_warnings = st.session_state.scenario_builder.get("parser_warnings", [])
    low_confidence = st.session_state.scenario_builder.get("low_confidence_fields", [])
    confidence = st.session_state.scenario_builder.get("field_confidence") or st.session_state.scenario_builder.get("parser_confidence", {})
    excerpts = st.session_state.scenario_builder.get("field_excerpts", {})
    if parser_warnings:
        for warning in parser_warnings:
            st.warning(warning)
    if low_confidence:
        st.info("Low-confidence parsed fields: " + ", ".join(low_confidence))
    if confidence:
        confidence_rows = [
            {"field": field, "confidence": f"{score:.0%}", "excerpt": excerpts.get(field, ""), "review": "low" if score < 0.55 else "ok"}
            for field, score in confidence.items()
        ]
        table(confidence_rows, ["field", "confidence", "excerpt", "review"], "No parser confidence metadata available.")
    if st.session_state.scenario_builder.get("phases"):
        st.markdown("**Parsed Phases**")
        table(st.session_state.scenario_builder.get("phases", []), None, "No phases detected.")
    confirm_cols = st.columns(2)
    if confirm_cols[0].button("Use Parsed Values", use_container_width=True):
        confirmed = api_post("/scenario-lab/confirm", {"scenario": st.session_state.scenario_builder}, {})
        if confirmed.get("scenario"):
            st.session_state.current_scenario = confirmed["scenario"]
            st.session_state.scenario_builder = st.session_state.current_scenario
            st.session_state.scenario_assumptions_confirmed = True
            st.session_state.scenario_parse_pending = False
            st.success(f"Parsed assumptions confirmed for analysis. Scenario ID: {st.session_state.scenario_builder.get('scenario_id')}")
    if confirm_cols[1].button("Edit Before Analysis", use_container_width=True):
        st.session_state.scenario_assumptions_confirmed = False
        st.session_state.scenario_parse_pending = True
        st.info("Edit the structured fields, then click Use Parsed Values before generating an outlook.")

    phases = (st.session_state.get("scenario_lab") or {}).get("phases", [])
    if phases:
        with st.expander("Reopen / Copy Previous Scenario"):
            labels = [f"{format_dashboard_timestamp(row.get('created_at'))} | {row.get('scenario', {}).get('scenario_name')}" for row in phases]
            selected = st.selectbox("Saved scenario", labels)
            if st.button("Copy Selected Scenario Into Editor"):
                set_current_scenario(dict(phases[labels.index(selected)].get("scenario", {})), status="Copied previous scenario into controls.", widgets_refreshed=True)
                st.rerun()

    if editor["save_summary"]:
        st.success("Scenario summary updated.")
    if editor["generate"]:
        if not st.session_state.get("scenario_assumptions_confirmed", False):
            st.warning("Review and confirm structured assumptions with Use Parsed Values before generating an HCP Outlook.")
            st.stop()
        with st.status("Generating HCP Outlook", expanded=True) as status:
            st.write("Reading current data")
            st.write("Retrieving historical analogs")
            st.write("Running specialist agents")
            st.write("Running model debate")
            st.write("Building final outlook")
            st.session_state.scenario_outlook = api_post(
                "/scenario-lab/outlook",
                {"scenario": st.session_state.scenario_builder, "sequence_name": "Manager Demo Scenario"},
                {},
            )
            refresh_artifacts()
            status.update(label="HCP outlook ready", state="complete")

    render_outlook(st.session_state.get("scenario_outlook", {}))

with tabs[2]:
    st.header("Expected Asset-Class Performance")
    render_outlook(st.session_state.get("scenario_outlook", {}))
    st.subheader("Latest Data Signals")
    signals = (st.session_state.get("signals") or {}).get("signals", [])
    table(signals, ["source", "name", "value", "direction", "interpretation"], "No data signals loaded yet.")

with tabs[5]:
    st.header("Investment Committee Report")
    reports = st.session_state.get("ic_reports", [])
    if not reports:
        st.info("No investment committee report yet. Generate an HCP Outlook from the Scenario Lab first.")
    else:
        labels = [f"{format_dashboard_timestamp(row.get('created_at'))} | {row.get('run_id')}" for row in reports]
        selected = st.selectbox("Report", labels, index=0)
        report = reports[labels.index(selected)]
        report_body = report.get("markdown", "")
        report_json = report.get("report", {})
        scenario_def = report_json.get("scenario_definition", {})
        st.caption(f"Run ID: {report.get('run_id')} | Run date: {format_dashboard_timestamp(report.get('created_at'))}")
        st.caption(format_relative_freshness(report.get("created_at")))
        meta_cols = st.columns(4)
        meta_cols[0].metric("Scenario", scenario_def.get("name", "Unknown"))
        meta_cols[1].metric("Data Mode", report_json.get("data_mode", "Unknown"))
        meta_cols[2].metric("Approval", "Pending" if report_json.get("approval_status", {}).get("pending_content") else "Approved")
        meta_cols[3].metric("Horizon", scenario_def.get("time_horizon", "n/a"))
        export_cols = st.columns(2)
        export_cols[0].download_button("Export Markdown", report_body, file_name=f"{report.get('run_id')}_ic_report.md", mime="text/markdown")
        pdf_bytes = api_get_bytes(f"/investment-committee/reports/{report.get('run_id')}/pdf")
        if pdf_bytes:
            export_cols[1].download_button(
                "Export PDF", pdf_bytes,
                file_name=f"{report.get('run_id')}_ic_report.pdf",
                mime="application/pdf",
            )
        else:
            export_cols[1].caption("PDF service unavailable; use browser print-to-PDF.")
        status = report_json.get("approval_status", {})
        if status:
            cols = st.columns(2)
            cols[0].metric("Approved Items", len(status.get("approved_content", [])))
            cols[1].metric("Pending Items", len(status.get("pending_content", [])))
        st.subheader("Executive View")
        st.write(report_json.get("executive_outlook") or "Not enough information to populate this section.")
        with st.expander("Detailed IC Memo", expanded=True):
            st.markdown(report_body)
        with st.expander("Traceability Viewer"):
            table(
                report_json.get("traceability", []),
                ["conclusion", "supporting_scenario_assumption", "supporting_data_source", "supporting_historical_analog", "supporting_agent_conclusion", "confidence_level"],
                "No traceability records saved for this report.",
            )
        with st.expander("Print-Friendly Notes"):
            st.markdown("Use the Markdown export for committee packets, or use browser print and Save as PDF for a PDF-ready view.")

with tabs[1]:
    st.header("Historical Analogs")
    outlook = st.session_state.get("scenario_outlook", {})
    analogs = outlook.get("historical_analogs", [])
    table(
        analogs,
        ["period", "similarity_score", "matching_conditions", "major_differences", "why_it_matters", "why_it_may_fail"],
        "No analogs yet. Generate an HCP Outlook first.",
    )
    if analogs:
        labels = [row["period"] for row in analogs]
        selected = st.selectbox("Analog performance detail", labels)
        analog = analogs[labels.index(selected)]
        table(analog.get("subsequent_asset_performance", []), None, "No performance summary stored for this analog.")
        st.caption("Historical analogs are reference cases, not forecasts.")

with tabs[3]:
    st.header("Suggested Portfolio")
    outlook = st.session_state.get("scenario_outlook", {})
    st.subheader("Long / Overweight")
    table(
        outlook.get("suggested_portfolio", {}).get("long_overweight", []),
        ["asset_class", "subsegment", "direction", "conviction", "expected_holding_horizon", "historical_analog_support", "current_data_support", "why_now", "main_catalyst", "main_risk", "confirmation_condition", "invalidation_condition", "portfolio_role", "tracking_benchmark_proxy"],
        "No long/overweight positions generated yet.",
    )
    st.subheader("Short / Underweight")
    table(
        outlook.get("suggested_portfolio", {}).get("short_underweight", []),
        ["asset_class", "subsegment", "direction", "conviction", "expected_holding_horizon", "historical_analog_support", "current_data_support", "why_now", "main_catalyst", "main_risk", "confirmation_condition", "invalidation_condition", "portfolio_role", "tracking_benchmark_proxy"],
        "No short/underweight positions generated yet.",
    )
    st.subheader("Unexpected / Non-Consensus Opportunities")
    table(outlook.get("unexpected_opportunities", []), None, "No opportunities met the evidence threshold.")
    st.caption("Research hypotheses for human review only. No trade execution is implied.")
    with st.expander("Human Approval Queue"):
        approvals = st.session_state.get("approvals", [])
        if approvals:
            for item in approvals:
                with st.container(border=True):
                    status_cols = st.columns([3, 1, 1])
                    status_cols[0].markdown(f"**{item['name']}**")
                    status_cols[1].caption(item["item_type"])
                    status_cols[2].caption(item["approval_status"])
                    st.write(item.get("reason", ""))
                    cols = st.columns(3)
                    if cols[0].button("Approve", key=f"approve_{item['id']}"):
                        api_post(f"/approvals/{item['id']}/approved")
                        refresh_artifacts()
                        st.rerun()
                    if cols[1].button("Reject", key=f"reject_{item['id']}"):
                        api_post(f"/approvals/{item['id']}/rejected")
                        refresh_artifacts()
                        st.rerun()
                    if cols[2].button("Needs Revision", key=f"revision_{item['id']}"):
                        api_post(f"/approvals/{item['id']}/needs_revision")
                        refresh_artifacts()
                        st.rerun()
        else:
            st.info("No approval items are currently pending.")

with tabs[4]:
    st.header("Portfolio Evolution")
    st.write("Build a 12-month theme across four sequential three-month phases.")
    if st.button("Build Demo 12-Month Theme", use_container_width=True):
        st.session_state.portfolio_evolution = api_post("/scenario-lab/demo", {}, {})
    evolution = st.session_state.get("portfolio_evolution", {})
    for phase in evolution.get("phases", []):
        with st.expander(f"{phase.get('window')} - {phase.get('phase_name')}", expanded=True):
            st.json(phase.get("scenario", {}))
            table(phase.get("historical_analogs", []), ["period", "similarity_score", "analog_weight", "matching_features", "important_differences"])
            portfolio = phase.get("suggested_portfolio", {})
            table(portfolio.get("long_overweight", []), ["subsegment", "direction", "conviction", "why_now"], "No longs.")
            table(portfolio.get("short_underweight", []), ["subsegment", "direction", "conviction", "why_now"], "No shorts.")
    st.subheader("Portfolio Changes Between Phases")
    table(evolution.get("portfolio_changes", []), None, "Build a theme to view phase changes.")

with tabs[6]:
    st.header("Outcomes & Evaluation")
    outcomes = st.session_state.get("outcomes", {})
    cols = st.columns(3)
    cols[0].metric("Hit Rate", f"{outcomes.get('hit_rate', 0):.0%}")
    cols[1].metric("Opportunity Outcomes", len(outcomes.get("opportunity_outcomes", [])))
    cols[2].metric("Hedge Outcomes", len(outcomes.get("hedge_outcomes", [])))

    st.subheader("Conviction Ranking Evaluation")
    ranking = st.session_state.get("conviction_ranking_eval", {})
    st.write(f"Status: {ranking.get('status', 'not_ready')} | Rows: {ranking.get('rows', 0)}")
    for warning in ranking.get("warnings", []):
        st.warning(warning)
    if ranking.get("report"):
        report = ranking["report"]
        metric_cols = st.columns(5)
        metric_cols[0].metric("Rank IC", f"{report.get('mean_ic', 0):+.3f}")
        metric_cols[1].metric("Kendall Tau", f"{report.get('mean_kendall', 0):+.3f}")
        metric_cols[2].metric("L/S Spread", f"{report.get('mean_ls_spread', 0):+.3f}")
        metric_cols[3].metric("Hit Rate", f"{report.get('hit_rate', 0):.0%}")
        metric_cols[4].metric("Tie Fraction", f"{report.get('mean_tie_fraction', 0):.0%}")
    else:
        st.info("Ranking evaluation appears after enough outcome-evaluated recommendations exist.")

    st.subheader("Outcome Tables")
    dashboard_table(outcomes.get("opportunity_outcomes", []), None, "No opportunity outcomes calculated yet.")
    dashboard_table(outcomes.get("hedge_outcomes", []), None, "No hedge outcomes calculated yet.")
    st.subheader("Calibration Report")
    if st.session_state.get("latest_calibration"):
        st.json(st.session_state.latest_calibration)
    else:
        st.info("No calibration report generated yet.")

with tabs[7]:
    st.header("Historical HCP Reports")
    uploaded = st.file_uploader("Upload historical report", type=["txt", "md", "eml", "pdf", "docx"], key="historical_upload")
    with st.form("historical_upload_form"):
        title = st.text_input("Document title", value="")
        author = st.text_input("Author", value="")
        publication_date = st.text_input("Original publication date", value="")
        report_type = st.selectbox("Report type", ["macro_report", "investment_committee", "hcp_report", "email_export"])
        approve = st.checkbox("Approve and index on import", value=False)
        import_clicked = st.form_submit_button("Import Historical Report")
    if uploaded is not None:
        preview = uploaded.getvalue()[:3000]
        st.text(preview.decode("utf-8", errors="ignore") if hasattr(preview, "decode") else str(preview))
    if import_clicked and uploaded is not None:
        upload_dir = ROOT / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / uploaded.name
        path.write_bytes(uploaded.getvalue())
        st.session_state.import_result = api_post(
            "/institutional/import",
            {
                "path": str(path),
                "approve": approve,
                "metadata": {
                    "title": title or uploaded.name,
                    "author": author or None,
                    "publication_date": publication_date or None,
                    "report_type": report_type,
                    "original_source": uploaded.name,
                },
            },
            {},
        )
        refresh_artifacts()
    if st.session_state.get("import_result"):
        st.success(f"Imported document: {st.session_state.import_result.get('document_id')}")
    dashboard_table(st.session_state.get("institutional_documents", []), None, "No historical HCP reports imported yet.")

with tabs[8]:
    st.header("System Monitor")
    scheduler = st.session_state.get("scheduler_status", {})
    cols = st.columns(4)
    latest_jobs = scheduler.get("latest_by_job", [])

    def latest_for(job_name: str) -> str:
        for row in latest_jobs:
            if row.get("job_name") == job_name:
                return row.get("finished_at") or row.get("started_at") or "never"
        return "never"

    cols[0].metric("Last Price Ingestion", format_dashboard_timestamp(latest_for("daily_price_ingestion")))
    cols[0].caption(format_relative_freshness(latest_for("daily_price_ingestion")))
    cols[1].metric("Last Outcome Eval", format_dashboard_timestamp(latest_for("horizon_based_outcome_evaluation")))
    cols[1].caption(format_relative_freshness(latest_for("horizon_based_outcome_evaluation")))
    cols[2].metric("Failed Jobs", len(scheduler.get("failed_jobs", [])))
    cols[3].metric("IC Reports", len(st.session_state.get("ic_reports", [])))

    st.subheader("FRED Connection")
    fred = st.session_state.get("fred_health", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Configured", "yes" if fred.get("configured") else "no")
    c2.metric("Reachable", "yes" if fred.get("reachable") else "no")
    c3.metric("Mode", fred.get("mode", "fallback"))
    c4.metric("Latest Pull", format_dashboard_timestamp(fred.get("latest_successful_pull")))
    c4.caption(format_relative_freshness(fred.get("latest_successful_pull")))
    message = fred.get("message", "FRED status unavailable")
    if message.startswith("Live Data Mode"):
        st.success(message.replace("Live Data Mode - FRED connected", "Live Data Mode — FRED connected"))
    else:
        st.warning(message)

    st.subheader("Local Scenario Parser")
    parser_health = st.session_state.get("scenario_parser_health", {})
    parser_mode = parser_health.get("scenario_parser_mode", "Rule-Based Parser Fallback")
    if parser_mode.startswith("Local Scenario Parser"):
        st.success("Local Scenario Parser — Connected")
    else:
        st.warning("Rule-Based Parser Fallback")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Ollama Reachable", "yes" if parser_health.get("reachable") else "no")
    p2.metric("Selected Model", parser_health.get("selected_model", "llama3.1:8b"))
    p3.metric("Latest Parse", format_dashboard_timestamp(parser_health.get("latest_successful_parse")))
    p4.metric("Fallback Count", parser_health.get("fallback_count", 0))
    st.caption(f"Latest parse duration: {parser_health.get('latest_parse_duration_ms') or 'n/a'} ms")
    if parser_health.get("latest_parser_error"):
        st.caption(f"Latest parser error: {parser_health.get('latest_parser_error')}")

    st.subheader("Scenario Lab State Debug")
    scenario_debug = st.session_state.get("scenario_options_debug", {})
    choice_counts = scenario_debug.get("choice_counts", {})
    debug_rows = [{"Field": field, "Choices": count} for field, count in choice_counts.items()]
    table(debug_rows, ["Field", "Choices"], "Scenario option counts are not available.")
    missing_fields = scenario_debug.get("missing_fields", [])
    api_missing_fields = scenario_debug.get("api_missing_fields", [])
    if missing_fields:
        st.error("Missing widget option fields: " + ", ".join(missing_fields))
    elif api_missing_fields:
        st.warning("The options API omitted fields; local safe options are active for: " + ", ".join(api_missing_fields))
    else:
        st.success("All required scenario option fields were returned by the API.")
    debug_tabs = st.tabs(["Current Scenario Object", "Parsed Response", "Scenario Options"])
    with debug_tabs[0]:
        st.json(st.session_state.get("current_scenario", {}))
        st.caption(f"Widget version: {st.session_state.get('scenario_widget_version', 0)}")
        st.caption(f"Version after latest parse assignment: {st.session_state.get('latest_widget_version_after_assignment', 'not available')}")
        st.json(st.session_state.get("latest_current_scenario_after_assignment", {}))
    with debug_tabs[1]:
        st.json(st.session_state.get("latest_parsed_response", {}))
    with debug_tabs[2]:
        st.caption("Raw scenario options API response")
        st.json(st.session_state.get("scenario_options_api_response"))
        st.caption("Scenario options used by Streamlit")
        st.json(st.session_state.get("scenario_options", {}))

    st.subheader("Data Sources & Model Providers")
    audit = st.session_state.get("source_audit", {"records": [], "comparison_readiness": {}})
    source_rows = source_status_rows(audit.get("records", []))
    table(
        source_rows,
        ["Source", "Category", "Connector", "Configured", "Reachable", "Mode", "Last Successful Pull", "Action Needed"],
        "No source audit data available yet.",
    )
    c1, c2, c3 = st.columns([1, 1, 2])
    if c1.button("Refresh Status", use_container_width=True):
        st.session_state.source_audit = api_get("/system/source-status", {"records": [], "comparison_readiness": {}})
        st.rerun()
    if c2.button("Test All Sources", use_container_width=True):
        st.session_state.source_audit = api_post("/system/source-status/test-all", {}, {"records": [], "comparison_readiness": {}})
        st.rerun()
    source_names = [row.get("source_name") for row in audit.get("records", [])]
    if source_names:
        selected_source = c3.selectbox("Source to test", source_names)
        if st.button("Test Connection", use_container_width=True):
            result = api_post(f"/system/source-status/test/{quote(selected_source, safe='')}", {}, {})
            st.session_state.single_source_test = result
            st.session_state.source_audit = api_get("/system/source-status", {"records": [], "comparison_readiness": {}})
            st.rerun()
    if st.session_state.get("single_source_test"):
        st.info(f"Latest source test: {st.session_state.single_source_test.get('source_name')} — {st.session_state.single_source_test.get('mode')}")

    st.subheader("Scenario Comparison Readiness")
    readiness = audit.get("comparison_readiness", {})
    st.metric("Overall Status", readiness.get("overall_status", "Demo Only"))
    readiness_rows = [
        {"Area": key.replace("_", " ").title(), "Status": value}
        for key, value in readiness.items()
        if key not in {"overall_status", "note"}
    ]
    table(readiness_rows, ["Area", "Status"], "No readiness data available yet.")
    if readiness.get("note"):
        st.caption(readiness["note"])

    with st.expander("Scheduled Jobs"):
        scheduled_jobs = format_timestamp_columns(
            scheduler.get("durable_jobs", []),
            ["next_run_time", "last_success_time", "last_failure_time", "created_at", "updated_at"],
        )
        table(scheduled_jobs, None, "No scheduled jobs configured yet.")
        for job in scheduler.get("durable_jobs", []):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"{job.get('job_name')} | next: {format_dashboard_timestamp(job.get('next_run_time'))} | retries: {job.get('retry_count')}")
            if c2.button("Run", key=f"run_{job.get('job_name')}"):
                api_post(f"/system/scheduler/run-job/{job.get('job_name')}", {"dry_run": False})
                refresh_artifacts()
                st.rerun()
            if c3.button("Dry Run", key=f"dry_{job.get('job_name')}"):
                api_post(f"/system/scheduler/run-job/{job.get('job_name')}", {"dry_run": True})
                refresh_artifacts()
                st.rerun()

    with st.expander("Technical Details"):
        st.subheader("Training & Evaluation Controls")
        c1, c2, c3 = st.columns(3)
        if c1.button("Build Training Dataset"):
            st.session_state.build_result = run_local_command(["python", "training/build_training_dataset.py"])
        if c2.button("Validate Dataset"):
            st.session_state.validation_result = run_local_command(["python", "training/validate_training_dataset.py"])
        if c3.button("Export Evaluation Dataset"):
            st.session_state.evaluation_export_result = api_post("/outcomes/export-evaluation-dataset", {}, {})
        c1, c2, c3 = st.columns(3)
        if c1.button("Ingest Prices"):
            st.session_state.price_ingest_result = api_post("/outcomes/ingest-prices", {"tickers": "IEF,SPY,GLD,VNQ,AMLP,BTC-USD", "start_date": "2020-01-01", "end_date": "2026-12-31"}, {})
        if c2.button("Evaluate Outcomes"):
            st.session_state.outcome_eval_result = api_post("/outcomes/evaluate", {}, {})
        if c3.button("Generate Calibration Report"):
            st.session_state.calibration_result = api_post("/outcomes/generate-calibration-report", {}, {})
        for key in ["build_result", "validation_result", "evaluation_export_result", "price_ingest_result", "outcome_eval_result", "calibration_result"]:
            if st.session_state.get(key):
                st.write({key: st.session_state[key]})
        st.subheader("Training Dataset Preview")
        preview = load_training_dataset_preview()
        st.write({"approved_examples": preview["count"], "path": preview["path"]})
        table(preview["latest"], None, "No approved dataset examples yet.")
        st.subheader("Historical Backtests")
        table(st.session_state.get("backtests", []), None, "No historical backtests available yet.")
        st.subheader("Readiness Reports")
        st.json({"fine_tuning": st.session_state.get("readiness", {}), "institutional": st.session_state.get("institutional_readiness", {})})
        st.subheader("Lessons Learned")
        st.json(st.session_state.get("lessons", {}))
        st.subheader("API Warnings")
        if st.session_state.api_warnings:
            for warning in st.session_state.api_warnings:
                st.warning(warning)
        else:
            st.success("No API warnings in this refresh.")
