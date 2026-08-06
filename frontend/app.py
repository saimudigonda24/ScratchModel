import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st


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


def api_post(path: str, payload: dict | None = None, default: Any = None) -> Any:
    try:
        response = requests.post(f"{API_URL}{path}", json=payload, timeout=90)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.session_state.api_warnings.append(f"POST {path}: {exc}")
        return default


def run_local_command(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=180)
    return {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def refresh_artifacts() -> None:
    st.session_state.signals = api_get("/signals", {"signals": [], "source_status": {}})
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
    st.session_state.scenario_options = api_get("/scenario-lab/options", {"presets": {}})
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
        return outlook["data_mode"]
    statuses = (st.session_state.get("signals") or {}).get("source_status", {})
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

    st.subheader("Cross-Asset Outlook")
    table(
        outlook["cross_asset_outlook"],
        ["asset_class", "expected_direction", "conviction", "time_horizon", "rationale", "main_risk"],
    )

    st.subheader("Top Opportunities")
    table(
        outlook["top_opportunities"],
        ["label", "name", "asset_class", "direction", "conviction_score", "expected_horizon", "proxy_ticker", "benchmark", "thesis", "catalyst", "invalidation_condition"],
    )

    st.subheader("Recommended Hedges")
    table(
        outlook["recommended_hedges"],
        ["label", "hedge_name", "risk_protected_against", "implementation_concept", "expected_cost_or_drag", "expected_payoff_condition", "major_limitation"],
    )

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
    presets = (st.session_state.get("scenario_options") or {}).get("presets", {})
    return dict(presets.get("Inflation Surprise + Strong Growth", {
        "scenario_name": "Inflation Surprise + Strong Growth",
        "scenario_description": "Inflation surprises higher, growth remains strong, and the Fed delays tightening.",
        "growth_outlook": "strong acceleration",
        "inflation_direction": "sharply higher",
        "inflation_surprise": "large upside surprise",
        "recession_probability": 0.2,
        "market_volatility": "normal",
        "central_bank_stance": "gradually tightening",
        "fed_position": "behind the curve",
        "labor_market": "overheating",
        "financial_conditions": "loose",
        "credit_stress": 2,
        "dollar_outlook": "moderately stronger",
        "commodity_shock": "energy shock",
        "equity_valuation": "expensive",
        "time_horizon": "7-14 months",
        "probability": 0.55,
        "countries_or_regions": ["U.S.", "Eurozone"],
        "custom_assumptions": "",
        "risks": [],
        "invalidation_triggers": [],
    }))


def option_index(options: list[str], value: Any) -> int:
    return options.index(value) if value in options else 0


def merge_builder_updates(builder: dict[str, Any]) -> dict[str, Any]:
    options = st.session_state.get("scenario_options") or {}
    region_options = options.get("countries_or_regions", [])
    existing_regions = builder.get("countries_or_regions", ["U.S."])
    selected_regions = [region for region in existing_regions if region in region_options]
    custom_regions = ", ".join(region for region in existing_regions if region not in region_options)
    with st.form("structured_scenario_editor"):
        st.subheader("Structured Scenario Summary")
        c1, c2 = st.columns(2)
        scenario_name = c1.text_input("Scenario name", value=builder.get("scenario_name", "Custom Macro Scenario"))
        scenario_description = c2.text_area("Scenario description", value=builder.get("scenario_description", ""), height=90)
        c1, c2, c3 = st.columns(3)
        growth = c1.selectbox("Growth", options.get("growth_outlook", []), index=option_index(options.get("growth_outlook", []), builder.get("growth_outlook")))
        inflation = c2.selectbox("Inflation", options.get("inflation_direction", []), index=option_index(options.get("inflation_direction", []), builder.get("inflation_direction")))
        inflation_surprise = c3.selectbox("Inflation surprise", options.get("inflation_surprise", []), index=option_index(options.get("inflation_surprise", []), builder.get("inflation_surprise")))
        c1, c2, c3 = st.columns(3)
        fed_stance = c1.selectbox("Fed / central bank stance", options.get("central_bank_stance", []), index=option_index(options.get("central_bank_stance", []), builder.get("central_bank_stance")))
        fed_position = c2.selectbox("Fed position", options.get("fed_position", []), index=option_index(options.get("fed_position", []), builder.get("fed_position")))
        labor = c3.selectbox("Labor market", options.get("labor_market", []), index=option_index(options.get("labor_market", []), builder.get("labor_market")))
        c1, c2, c3 = st.columns(3)
        financial = c1.selectbox("Financial conditions", options.get("financial_conditions", []), index=option_index(options.get("financial_conditions", []), builder.get("financial_conditions")))
        volatility = c2.selectbox("Market volatility", options.get("market_volatility", []), index=option_index(options.get("market_volatility", []), builder.get("market_volatility")))
        credit_stress = c3.slider("Credit stress", 0, 10, int(builder.get("credit_stress", 3)))
        c1, c2, c3 = st.columns(3)
        dollar = c1.selectbox("Dollar outlook", options.get("dollar_outlook", []), index=option_index(options.get("dollar_outlook", []), builder.get("dollar_outlook")))
        commodity = c2.selectbox("Commodity shock", options.get("commodity_shock", []), index=option_index(options.get("commodity_shock", []), builder.get("commodity_shock")))
        valuation = c3.selectbox("Equity valuation", options.get("equity_valuation", []), index=option_index(options.get("equity_valuation", []), builder.get("equity_valuation")))
        c1, c2, c3 = st.columns(3)
        horizon = c1.selectbox("Time horizon", options.get("time_horizon", []), index=option_index(options.get("time_horizon", []), builder.get("time_horizon")))
        recession = c2.slider("Recession probability", 0.0, 1.0, float(builder.get("recession_probability", 0.3)), 0.01)
        probability = c3.slider("Scenario probability", 0.0, 1.0, float(builder.get("probability", 0.5)), 0.01)
        c1, c2 = st.columns(2)
        countries = c1.multiselect("Countries/regions", region_options, default=selected_regions)
        custom_countries = c2.text_input("Custom regions", value=custom_regions)
        custom_assumptions = st.text_area("Custom assumptions", value=builder.get("custom_assumptions", ""), height=90)
        risks = st.text_area("Risks", value="\n".join(builder.get("risks", [])), height=90)
        invalidation = st.text_area("Invalidation triggers", value="\n".join(builder.get("invalidation_triggers", [])), height=90)
        c1, c2 = st.columns([1, 1])
        save_summary = c1.form_submit_button("Update Scenario Summary", use_container_width=True)
        generate = c2.form_submit_button("Generate HCP Outlook", type="primary", use_container_width=True)
    regions = countries + [item.strip() for item in custom_countries.split(",") if item.strip()]
    updated = {
        "scenario_name": scenario_name,
        "scenario_description": scenario_description,
        "growth_outlook": growth,
        "inflation_direction": inflation,
        "inflation_surprise": inflation_surprise,
        "central_bank_stance": fed_stance,
        "fed_position": fed_position,
        "labor_market": labor,
        "financial_conditions": financial,
        "market_volatility": volatility,
        "credit_stress": credit_stress,
        "dollar_outlook": dollar,
        "commodity_shock": commodity,
        "equity_valuation": valuation,
        "time_horizon": horizon,
        "recession_probability": recession,
        "probability": probability,
        "countries_or_regions": regions,
        "custom_assumptions": custom_assumptions,
        "risks": [item.strip() for item in risks.splitlines() if item.strip()],
        "invalidation_triggers": [item.strip() for item in invalidation.splitlines() if item.strip()],
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
        "Current Outlook",
        "Investment Committee Report",
        "Historical Analogs",
        "Opportunities & Hedges",
        "Outcomes & Evaluation",
        "Historical HCP Reports",
        "System Monitor",
    ]
)

with tabs[0]:
    st.header("Scenario Lab")
    st.write("Describe a macro scenario in plain English or build one with controls, then review the structured assumptions before generating an HCP outlook.")
    st.session_state.setdefault("scenario_builder", default_scenario())
    options = st.session_state.get("scenario_options") or {"presets": {}}

    input_tabs = st.tabs(["Describe a Scenario", "Build a Scenario"])
    with input_tabs[0]:
        scenario_text = st.text_area(
            "Plain-English scenario",
            value="Inflation surprises higher, growth remains strong, and the Fed delays tightening.",
            height=160,
        )
        if st.button("Parse Scenario", use_container_width=True):
            parsed = api_post("/scenario-lab/parse", {"text": scenario_text}, {})
            if parsed.get("scenario"):
                st.session_state.scenario_builder = parsed["scenario"]
                st.success("Scenario parsed. Review and edit the extracted fields below.")
        st.caption("The parser is rule-based for the demo. You can edit every extracted field before analysis.")

    with input_tabs[1]:
        st.markdown("**Scenario Presets**")
        preset_names = list(options.get("presets", {}).keys())
        for row_start in range(0, len(preset_names), 5):
            cols = st.columns(5)
            for col, name in zip(cols, preset_names[row_start:row_start + 5]):
                if col.button(name, key=f"preset_{name}", use_container_width=True):
                    st.session_state.scenario_builder = dict(options["presets"][name])
                    st.success(f"Loaded preset: {name}")
        st.caption("Presets populate the controls, but all fields remain editable.")

    editor = merge_builder_updates(st.session_state.scenario_builder)
    st.session_state.scenario_builder = editor["scenario"]
    summary = api_post("/scenario-lab/summary", {"scenario": st.session_state.scenario_builder}, {"summary": {}})
    st.markdown("**Pre-Analysis Summary**")
    summary_rows = [{"assumption": key, "value": value} for key, value in summary.get("summary", {}).items()]
    table(summary_rows, ["assumption", "value"], "No scenario summary available yet.")

    phases = (st.session_state.get("scenario_lab") or {}).get("phases", [])
    if phases:
        with st.expander("Reopen / Copy Previous Scenario"):
            labels = [f"{row.get('created_at')} | {row.get('scenario', {}).get('scenario_name')}" for row in phases]
            selected = st.selectbox("Saved scenario", labels)
            if st.button("Copy Selected Scenario Into Editor"):
                st.session_state.scenario_builder = dict(phases[labels.index(selected)].get("scenario", {}))
                st.rerun()

    if editor["save_summary"]:
        st.success("Scenario summary updated.")
    if editor["generate"]:
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

with tabs[1]:
    st.header("Current Outlook")
    render_outlook(st.session_state.get("scenario_outlook", {}))
    st.subheader("Latest Data Signals")
    signals = (st.session_state.get("signals") or {}).get("signals", [])
    table(signals, ["source", "name", "value", "direction", "interpretation"], "No data signals loaded yet.")

with tabs[2]:
    st.header("Investment Committee Report")
    reports = st.session_state.get("ic_reports", [])
    if not reports:
        st.info("No investment committee report yet. Generate an HCP Outlook from the Scenario Lab first.")
    else:
        labels = [f"{row.get('created_at', '')[:19]} | {row.get('run_id')}" for row in reports]
        selected = st.selectbox("Report", labels, index=0)
        report = reports[labels.index(selected)]
        report_body = report.get("markdown", "")
        st.caption(f"Run ID: {report.get('run_id')} | Run date: {report.get('created_at')}")
        st.download_button("Export Markdown", report_body, file_name=f"{report.get('run_id')}_ic_report.md", mime="text/markdown")
        st.info("PDF-ready view: use your browser print command and choose Save as PDF.")
        status = report.get("report", {}).get("approval_status", {})
        if status:
            cols = st.columns(2)
            cols[0].metric("Approved Items", len(status.get("approved_content", [])))
            cols[1].metric("Pending Items", len(status.get("pending_content", [])))
        st.markdown(report_body)

with tabs[3]:
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

with tabs[4]:
    st.header("Opportunities & Hedges")
    outlook = st.session_state.get("scenario_outlook", {})
    st.subheader("Ranked Opportunities")
    table(
        outlook.get("top_opportunities", []),
        ["label", "name", "asset_class", "direction", "conviction_score", "expected_horizon", "proxy_ticker", "benchmark", "conditions_for_entry", "conditions_for_exit", "risks", "invalidation_condition"],
        "No opportunities generated yet.",
    )
    st.subheader("Recommended Hedges")
    table(
        outlook.get("recommended_hedges", []),
        ["label", "hedge_name", "risk_protected_against", "implementation_concept", "expected_cost_or_drag", "expected_payoff_condition", "major_limitation"],
        "No hedges generated yet.",
    )
    with st.expander("Human Approval Queue"):
        approvals = st.session_state.get("approvals", [])
        if approvals:
            for item in approvals:
                with st.expander(f"{item['name']} | {item['item_type']} | {item['approval_status']}"):
                    st.markdown(f"**{item['name']}** | {item['item_type']} | {item['approval_status']}")
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

with tabs[5]:
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
    table(outcomes.get("opportunity_outcomes", []), None, "No opportunity outcomes calculated yet.")
    table(outcomes.get("hedge_outcomes", []), None, "No hedge outcomes calculated yet.")
    st.subheader("Calibration Report")
    if st.session_state.get("latest_calibration"):
        st.json(st.session_state.latest_calibration)
    else:
        st.info("No calibration report generated yet.")

with tabs[6]:
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
    table(st.session_state.get("institutional_documents", []), None, "No historical HCP reports imported yet.")

with tabs[7]:
    st.header("System Monitor")
    scheduler = st.session_state.get("scheduler_status", {})
    cols = st.columns(4)
    latest_jobs = scheduler.get("latest_by_job", [])

    def latest_for(job_name: str) -> str:
        for row in latest_jobs:
            if row.get("job_name") == job_name:
                return row.get("finished_at") or row.get("started_at") or "never"
        return "never"

    cols[0].metric("Last Price Ingestion", latest_for("daily_price_ingestion"))
    cols[1].metric("Last Outcome Eval", latest_for("horizon_based_outcome_evaluation"))
    cols[2].metric("Failed Jobs", len(scheduler.get("failed_jobs", [])))
    cols[3].metric("IC Reports", len(st.session_state.get("ic_reports", [])))

    with st.expander("Scheduled Jobs"):
        table(scheduler.get("durable_jobs", []), None, "No scheduled jobs configured yet.")
        for job in scheduler.get("durable_jobs", []):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"{job.get('job_name')} | next: {job.get('next_run_time')} | retries: {job.get('retry_count')}")
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
