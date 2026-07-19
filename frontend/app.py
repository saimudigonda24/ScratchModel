import os
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("HCP_API_URL", "http://localhost:8000")
ROOT = Path(__file__).resolve().parents[1]
TRAINING_DATASET = ROOT / "datasets" / "cleaned_examples" / "hcp_macro_training.jsonl"


def api_get(path: str) -> Any:
    response = requests.get(f"{API_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict | None = None) -> Any:
    response = requests.post(f"{API_URL}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def run_workflow(report_text: str | None, report_title: str = "Dashboard input") -> dict[str, Any]:
    return api_post("/workflow/run", {"report_text": report_text, "report_title": report_title})


def refresh_artifacts() -> None:
    st.session_state.signals = api_get("/signals")
    st.session_state.training_examples = api_get("/artifacts/training-examples")
    st.session_state.evaluations = api_get("/artifacts/evaluations")
    st.session_state.reports = api_get("/history/reports")
    st.session_state.thesis_history = api_get("/history/thesis")
    st.session_state.debates = api_get("/history/debates")
    st.session_state.approvals = api_get("/approvals")
    st.session_state.outcomes = api_get("/outcomes")
    st.session_state.conviction_ranking_eval = api_get("/outcomes/conviction-ranking-evaluation")
    st.session_state.proxy_mappings = api_get("/outcomes/proxy-mappings")
    st.session_state.scheduler_status = api_get("/system/scheduler")
    st.session_state.latest_calibration = api_get("/outcomes/latest-calibration-report")
    st.session_state.readiness = api_get("/training/fine-tuning-readiness")
    st.session_state.institutional_readiness = api_get("/institutional/readiness")
    st.session_state.institutional_documents = api_get("/institutional/documents")
    st.session_state.historical_postmortems = api_get("/institutional/postmortems")
    st.session_state.ic_reports = api_get("/investment-committee/reports")
    st.session_state.scenario_lab = api_get("/scenario-lab")
    st.session_state.regimes = api_get("/regimes")
    st.session_state.backtests = api_get("/backtests/historical")
    st.session_state.lessons = api_get("/memory/lessons")


def run_local_command(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=120)
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def load_training_dataset_preview(limit: int = 5) -> dict[str, Any]:
    if not TRAINING_DATASET.exists():
        return {"count": 0, "latest": [], "path": str(TRAINING_DATASET)}
    rows = [json.loads(line) for line in TRAINING_DATASET.read_text().splitlines() if line.strip()]
    latest = rows[-limit:]
    return {
        "count": len(rows),
        "latest": latest,
        "path": str(TRAINING_DATASET),
        "source_run_ids": [row.get("metadata", {}).get("run_id") for row in latest],
        "created_at": [row.get("metadata", {}).get("created_at") for row in latest],
    }


st.set_page_config(page_title="HCP Macro Theme AI", layout="wide")
st.title("HCP Macro Theme AI Investment System")
st.caption("Research hypotheses only. Human approval required. No trade execution.")

with st.sidebar:
    st.header("Run Analysis")
    uploaded = st.file_uploader("Upload HCP report text", type=["txt", "md"])
    default_text = (
        "HCP dashboard note: inflation is moderating, growth is slowing, central banks are becoming more two-sided, "
        "and the investment committee wants ranked cross-asset ideas with hedges."
    )
    report_text = st.text_area("Macro report input", value=default_text, height=220)
    if uploaded is not None:
        report_text = uploaded.read().decode("utf-8", errors="ignore")
    report_title = st.text_input("Report title", value="Dashboard input")
    run_button = st.button("Run New Analysis", type="primary", use_container_width=True)
    refresh_button = st.button("Refresh Saved Data", use_container_width=True)
    export_button = st.button("Export Approved JSONL", use_container_width=True)
    build_dataset_button = st.button("Build Training Dataset", use_container_width=True)
    validate_dataset_button = st.button("Validate Dataset", use_container_width=True)
    export_eval_button = st.button("Export Evaluation Dataset", use_container_width=True)
    ingest_prices_button = st.button("Ingest Prices", use_container_width=True)
    evaluate_outcomes_button = st.button("Evaluate Outcomes", use_container_width=True)
    calibration_button = st.button("Generate Calibration Report", use_container_width=True)
    scheduler_dry_run_button = st.button("Run Scheduler Dry Run", use_container_width=True)
    run_backtests_button = st.button("Run Historical Backtests", use_container_width=True)
    generate_lessons_button = st.button("Generate Lessons Learned", use_container_width=True)
    scenario_demo_button = st.button("Create Scenario Demo", use_container_width=True)

try:
    if "result" not in st.session_state or run_button:
        st.session_state.result = run_workflow(report_text, report_title)
        refresh_artifacts()
    elif refresh_button:
        refresh_artifacts()
    if export_button:
        st.session_state.export_result = api_post("/training/export-approved")
        refresh_artifacts()
    if build_dataset_button:
        st.session_state.build_result = run_local_command(["python", "training/build_training_dataset.py"])
    if validate_dataset_button:
        st.session_state.validation_result = run_local_command(["python", "training/validate_training_dataset.py"])
    if export_eval_button:
        st.session_state.evaluation_export_result = api_post("/outcomes/export-evaluation-dataset")
    if ingest_prices_button:
        st.session_state.price_ingest_result = api_post(
            "/outcomes/ingest-prices",
            {"tickers": "IEF,SPY,GLD,VNQ,AMLP,BTC-USD", "start_date": "2020-01-01", "end_date": "2026-12-31"},
        )
        refresh_artifacts()
    if evaluate_outcomes_button:
        st.session_state.outcome_eval_result = api_post("/outcomes/evaluate", {})
        refresh_artifacts()
    if calibration_button:
        st.session_state.calibration_result = api_post("/outcomes/generate-calibration-report")
        refresh_artifacts()
    if scheduler_dry_run_button:
        st.session_state.scheduler_run_result = api_post("/system/scheduler/run", {"dry_run": True})
        refresh_artifacts()
    if run_backtests_button:
        st.session_state.backtest_run_result = api_post("/backtests/run-standard-suite")
        refresh_artifacts()
    if generate_lessons_button:
        st.session_state.lessons_result = api_post("/memory/generate-lessons")
        refresh_artifacts()
    if scenario_demo_button:
        st.session_state.scenario_demo_result = api_post("/scenario-lab/demo")
        refresh_artifacts()
    st.session_state.error = None
except requests.RequestException as exc:
    st.session_state.error = str(exc)

if st.session_state.get("error"):
    st.error(f"Backend unavailable: {st.session_state.error}")
    st.info("Start the backend with: uvicorn app.main:app --app-dir backend --port 8000")
    st.stop()

result = st.session_state.result
thesis = result["thesis"]

if st.session_state.get("export_result"):
    export = st.session_state.export_result
    st.success(f"Exported {export['count']} approved training examples to {export['path']}")
if st.session_state.get("build_result"):
    build = st.session_state.build_result
    (st.success if build["returncode"] == 0 else st.error)(build["stdout"] or build["stderr"])
if st.session_state.get("validation_result"):
    validation = st.session_state.validation_result
    (st.success if validation["returncode"] == 0 else st.error)(validation["stdout"] or validation["stderr"])
if st.session_state.get("evaluation_export_result"):
    export = st.session_state.evaluation_export_result
    st.success(f"Exported {export['count']} outcome rows to {export['path']}")
if st.session_state.get("price_ingest_result"):
    st.success(f"Price ingestion complete: {st.session_state.price_ingest_result}")
if st.session_state.get("outcome_eval_result"):
    st.success(f"Outcome evaluation complete: {st.session_state.outcome_eval_result}")
if st.session_state.get("calibration_result"):
    st.success(f"Calibration report generated: {st.session_state.calibration_result.get('path')}")
if st.session_state.get("scheduler_run_result"):
    st.success(f"Scheduler dry run complete: {st.session_state.scheduler_run_result}")

tabs = st.tabs([
    "Current Run",
    "Opportunities",
    "Debate",
    "Approvals",
    "History",
    "Training/Evals",
    "Outcomes & Evaluation",
    "System Monitor",
    "Historical Backtests",
    "Historical HCP Reports",
    "Scenario Lab",
])

with tabs[0]:
    left, mid, right, score = st.columns(4)
    left.metric("Base Case", result["probability_bands"]["base_case"])
    mid.metric("Bull Case", result["probability_bands"]["bull_case"])
    right.metric("Bear/Tail Case", result["probability_bands"]["bear_tail_case"])
    score.metric("Conviction", result["conviction_score"])

    st.subheader("Current Macro Thesis")
    st.write(f"**{thesis['title']}**")
    st.write(thesis["base_case"]["summary"])

    case_cols = st.columns(3)
    for col, case_name, label in zip(case_cols, ["base_case", "bull_case", "bear_tail_case"], ["Base", "Bull", "Bear/Tail"]):
        with col:
            case = thesis[case_name]
            st.markdown(f"**{label}: {case['probability']:.0%}**")
            st.write(case["summary"])

    st.subheader("Latest Data Signals")
    signals_df = pd.DataFrame(st.session_state.signals["signals"])
    st.dataframe(signals_df[["source", "name", "value", "direction", "interpretation"]], use_container_width=True)

    st.subheader("Evaluation Scorecard")
    eval_result = result.get("evaluation_result")
    if eval_result:
        cols = st.columns(4)
        cols[0].metric("Reasoning", eval_result.get("reasoning_quality", 0))
        cols[1].metric("Macro", eval_result["macro_consistency"])
        cols[2].metric("Evidence", eval_result["evidence_quality"])
        cols[3].metric("Cross-Asset", eval_result["cross_asset_reasoning"])
        cols = st.columns(4)
        cols[0].metric("Risk", eval_result["risk_awareness"])
        cols[1].metric("Hedges", eval_result["hedge_quality"])
        cols[2].metric("Clarity", eval_result["clarity"])
        cols[3].metric("Actionability", eval_result["actionability"])

with tabs[1]:
    st.subheader("Ranked Research Hypotheses")
    opportunities_df = pd.DataFrame(result["ranked_opportunities"])
    st.dataframe(
        opportunities_df[
            [
                "asset_class",
                "name",
                "probability_band",
                "conviction_score",
                "thesis_fit",
                "catalyst",
                "human_approval_status",
            ]
        ],
        use_container_width=True,
    )
    names = [item["name"] for item in result["ranked_opportunities"]]
    selected_name = st.selectbox("Opportunity detail", names)
    selected = next(item for item in result["ranked_opportunities"] if item["name"] == selected_name)
    st.write(f"**Research hypothesis:** {selected['thesis']}")
    st.write(f"**Asset class:** {selected['asset_class']}")
    st.write(f"**Catalyst:** {selected['catalyst']}")
    st.write(f"**Risks:** {selected['risks']}")
    st.write(f"**Confirming data:** {selected['confirming_data']}")
    st.write(f"**Invalidating data:** {selected['invalidating_data']}")

    st.subheader("Hedge Menu")
    hedge_df = pd.DataFrame(result["ranked_hedge_ideas"])
    st.dataframe(hedge_df[["asset_class", "name", "conviction_score", "asymmetry", "human_approval_status"]], use_container_width=True)

with tabs[2]:
    st.subheader("Model Debate Detail")
    model_debate = result.get("model_debate")
    if model_debate:
        st.write(f"**Judge summary:** {model_debate['judge_summary']}")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Agreements**")
            for item in model_debate["agreements"]:
                st.markdown(f"- {item}")
            st.markdown("**Strongest Opportunities**")
            for item in model_debate["strongest_opportunities"]:
                st.markdown(f"- {item}")
        with col_b:
            st.markdown("**Disagreements**")
            for item in model_debate["disagreements"]:
                st.markdown(f"- {item}")
            st.markdown("**Hidden Risks**")
            for item in model_debate["hidden_risks"]:
                st.markdown(f"- {item}")
        for answer in model_debate["raw_answers"]:
            with st.expander(f"{answer['provider']} / {answer['model']} raw answer"):
                st.write(answer["content"])
                st.caption(f"fallback={answer['used_fallback']} error={answer.get('error')}")

with tabs[3]:
    st.subheader("Human Approval Queue")
    approvals = st.session_state.get("approvals", [])
    if approvals:
        for item in approvals:
            with st.expander(f"#{item['id']} {item['priority'].upper()} - {item['name']} [{item['approval_status']}]"):
                st.write(item["reason"])
                st.write(f"**Run ID:** {item['run_id']}")
                st.write(f"**Type:** {item['item_type']}")
                st.write(f"**Asset class:** {item.get('asset_class', 'cross_asset')}")
                st.write(f"**Thesis fit:** {item.get('thesis_fit', '')}")
                st.write(f"**Current approval status:** {item['approval_status']}")
                st.markdown("**Evidence**")
                for value in item.get("evidence", []) or ["No evidence attached"]:
                    st.markdown(f"- {value}")
                st.markdown("**Risks**")
                for value in item.get("risks", []) or ["No risks attached"]:
                    st.markdown(f"- {value}")
                st.markdown("**Confirming Data**")
                for value in item.get("confirming_data", []) or ["No confirming data attached"]:
                    st.markdown(f"- {value}")
                st.markdown("**Invalidating Data**")
                for value in item.get("invalidating_data", []) or ["No invalidating data attached"]:
                    st.markdown(f"- {value}")
                debate_notes = item.get("model_debate_notes", {})
                st.markdown("**Model Debate Notes**")
                if debate_notes.get("judge_summary"):
                    st.write(debate_notes["judge_summary"])
                for label in ["agreements", "disagreements", "hidden_risks", "final_ranked_ideas"]:
                    values = debate_notes.get(label, [])
                    if values:
                        st.write(label.replace("_", " ").title())
                        for value in values:
                            st.markdown(f"- {value}")
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
        st.write("No approval items saved yet.")

with tabs[4]:
    st.subheader("Past Reports")
    st.dataframe(pd.DataFrame(st.session_state.get("reports", [])), use_container_width=True)

    st.subheader("Thesis History")
    thesis_rows = [
        {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "title": row["title"],
            "base_case": row["thesis"]["base_case"]["summary"],
        }
        for row in st.session_state.get("thesis_history", [])
    ]
    st.dataframe(pd.DataFrame(thesis_rows), use_container_width=True)

    st.subheader("Saved Debate Outputs")
    debate_rows = [
        {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "judge_summary": row["payload"]["judge_summary"],
        }
        for row in st.session_state.get("debates", [])
    ]
    st.dataframe(pd.DataFrame(debate_rows), use_container_width=True)

with tabs[5]:
    st.subheader("Saved Training Candidates")
    training_examples = st.session_state.get("training_examples", [])
    if training_examples:
        training_df = pd.DataFrame(
            [
                {
                    "example_id": row.get("example_id"),
                    "task": row.get("task"),
                    "approval_status": row.get("metadata", {}).get("approval_status"),
                    "source": row.get("metadata", {}).get("source"),
                    "path": row.get("_path"),
                }
                for row in training_examples
            ]
        )
        st.dataframe(training_df, use_container_width=True)
    else:
        st.write("No saved training candidates yet.")

    st.subheader("Evaluation Results")
    st.dataframe(pd.DataFrame(st.session_state.get("evaluations", [])), use_container_width=True)

    st.subheader("Training Dataset Preview")
    preview = load_training_dataset_preview()
    cols = st.columns(3)
    cols[0].metric("Approved Examples", preview["count"])
    cols[1].metric("Latest Rows", len(preview["latest"]))
    cols[2].write(preview["path"])
    if preview["latest"]:
        preview_rows = [
            {
                "example_id": row.get("example_id"),
                "source_run_id": row.get("metadata", {}).get("run_id"),
                "date_created": row.get("metadata", {}).get("created_at"),
                "task": row.get("task"),
            }
            for row in preview["latest"]
        ]
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True)
        for row in preview["latest"]:
            with st.expander(f"JSONL example {row.get('example_id')}"):
                st.json(row)
    else:
        st.write("No approved dataset examples yet. Approve a full run, then click Build Training Dataset.")

with tabs[6]:
    st.subheader("Outcomes & Evaluation")
    outcomes = st.session_state.get("outcomes", {})
    cols = st.columns(3)
    cols[0].metric("Hit Rate", f"{outcomes.get('hit_rate', 0):.0%}")
    cols[1].metric("Opportunity Outcomes", len(outcomes.get("opportunity_outcomes", [])))
    cols[2].metric("Hedge Outcomes", len(outcomes.get("hedge_outcomes", [])))

    st.subheader("Approved Opportunities Awaiting Outcome Tracking")
    awaiting = outcomes.get("approved_opportunities_awaiting_outcomes", [])
    st.dataframe(pd.DataFrame(awaiting), use_container_width=True)
    if awaiting:
        st.markdown("**Manual Proxy Override**")
        labels = [f"{item['run_id']} | {item['name']}" for item in awaiting]
        selected_label = st.selectbox("Opportunity or hedge", labels)
        selected_item = awaiting[labels.index(selected_label)]
        with st.form("proxy_override_form"):
            proxy_ticker = st.text_input("Proxy ticker", value=selected_item.get("proxy_ticker") or "SPY")
            benchmark_ticker = st.text_input("Benchmark ticker", value="SPY")
            expected_direction = st.selectbox("Expected direction", ["long", "short"], index=0)
            start_date = st.text_input("Start date", value=str(selected_item.get("created_at", ""))[:10])
            target_horizon = st.text_input("Target horizon months", value="7,14")
            notes = st.text_area("Notes", value="")
            submitted = st.form_submit_button("Save Override")
            if submitted:
                horizon = [int(value.strip()) for value in target_horizon.split(",") if value.strip()]
                saved = api_post(
                    "/outcomes/proxy-override",
                    {
                        "run_id": selected_item["run_id"],
                        "item_type": "opportunity",
                        "item_id": selected_item["name"],
                        "proxy_ticker": proxy_ticker,
                        "benchmark_ticker": benchmark_ticker,
                        "expected_direction": expected_direction,
                        "start_date": start_date,
                        "target_horizon_months": horizon,
                        "notes": notes,
                    },
                )
                st.success(f"Saved override: {saved}")
                refresh_artifacts()

    st.subheader("Proxy Ticker Mapping")
    st.dataframe(pd.DataFrame(st.session_state.get("proxy_mappings", [])), use_container_width=True)

    st.subheader("Realized Return Table")
    st.dataframe(pd.DataFrame(outcomes.get("opportunity_outcomes", [])), use_container_width=True)

    st.subheader("Hedge Effectiveness")
    st.dataframe(pd.DataFrame(outcomes.get("hedge_outcomes", [])), use_container_width=True)

    st.subheader("Hedge Stress-Window Viewer")
    hedge_rows = outcomes.get("hedge_outcomes", [])
    if hedge_rows:
        selected_hedge = st.selectbox("Hedge outcome", [f"{row.get('run_id')} | {row.get('hedge_id')}" for row in hedge_rows])
        hedge = hedge_rows[[f"{row.get('run_id')} | {row.get('hedge_id')}" for row in hedge_rows].index(selected_hedge)]
        st.json({
            "stress_window": hedge.get("stress_window"),
            "hedge_effectiveness": hedge.get("hedge_effectiveness"),
            "notes": hedge.get("notes"),
            "quality_score": hedge.get("outcome_quality_score"),
            "eligible_for_fine_tuning": hedge.get("eligible_for_fine_tuning"),
        })

    st.subheader("Thesis-Level Outcomes")
    thesis_rows = []
    for row in outcomes.get("thesis_outcomes", []):
        parsed = dict(row)
        parsed["outcome_json"] = str(parsed.get("outcome_json", ""))[:500]
        thesis_rows.append(parsed)
    st.dataframe(pd.DataFrame(thesis_rows), use_container_width=True)

    st.subheader("Forecast Calibration")
    st.dataframe(pd.DataFrame(outcomes.get("forecast_outcomes", [])), use_container_width=True)

    st.subheader("Conviction Ranking Evaluation")
    ranking_eval = st.session_state.get("conviction_ranking_eval", {})
    status = ranking_eval.get("status", "unknown")
    rows = ranking_eval.get("rows", 0)
    st.write({"status": status, "evaluated_rows": rows})
    for warning in ranking_eval.get("warnings", []):
        st.warning(warning)
    report = ranking_eval.get("report")
    if report:
        metric_cols = st.columns(5)
        metric_cols[0].metric("Rank IC", f"{report.get('mean_ic', 0):+.3f}")
        metric_cols[1].metric("Kendall Tau", f"{report.get('mean_kendall', 0):+.3f}")
        metric_cols[2].metric("L/S Spread", f"{report.get('mean_ls_spread', 0):+.3f}")
        metric_cols[3].metric("Hit Rate", f"{report.get('hit_rate', 0):.0%}")
        metric_cols[4].metric("Tie Fraction", f"{report.get('mean_tie_fraction', 0):.0%}")
        st.json(
            {
                "ic_t_stat": report.get("ic_t_stat"),
                "permutation_p": report.get("permutation_p"),
                "bucket_returns": report.get("bucket_returns"),
                "point_in_time_validation": "Return windows must begin no earlier than recommendation timestamp plus execution lag.",
            }
        )
    else:
        st.info("Ranking evaluation will appear after enough outcome-evaluated recommendations exist.")

    st.subheader("Hit Rate By Asset Class")
    hit_rows = [{"asset_class": key, "hit_rate": value} for key, value in outcomes.get("hit_rate_by_asset_class", {}).items()]
    st.dataframe(pd.DataFrame(hit_rows), use_container_width=True)

    st.subheader("Average Return By Conviction Bucket")
    bucket_rows = [
        {"conviction_bucket": key, "average_return": value}
        for key, value in outcomes.get("average_return_by_conviction_bucket", {}).items()
    ]
    st.dataframe(pd.DataFrame(bucket_rows), use_container_width=True)

    st.subheader("Best Historical Recommendations")
    st.dataframe(pd.DataFrame(outcomes.get("best_recommendations", [])), use_container_width=True)

    st.subheader("Worst Historical Recommendations")
    st.dataframe(pd.DataFrame(outcomes.get("worst_recommendations", [])), use_container_width=True)

    st.subheader("Calibration Report Viewer")
    if st.session_state.get("latest_calibration"):
        st.json(st.session_state.latest_calibration)
    else:
        st.write("No calibration report generated yet.")

    st.subheader("Regime Labels")
    st.dataframe(pd.DataFrame(st.session_state.get("regimes", [])), use_container_width=True)

with tabs[7]:
    st.subheader("System Monitor")
    scheduler_status = st.session_state.get("scheduler_status", {})
    st.markdown("**Scheduled Job Status**")
    st.dataframe(pd.DataFrame(scheduler_status.get("durable_jobs", [])), use_container_width=True)

    st.markdown("**Manual Job Controls**")
    durable_jobs = scheduler_status.get("durable_jobs", [])
    for job in durable_jobs:
        cols = st.columns([3, 1, 1, 1])
        cols[0].write(f"{job.get('job_name')} | next: {job.get('next_run_time')} | retries: {job.get('retry_count')}")
        if cols[1].button("Run", key=f"run_{job.get('job_name')}"):
            st.session_state[f"manual_job_{job.get('job_name')}"] = api_post(f"/system/scheduler/run-job/{job.get('job_name')}", {"dry_run": False})
            refresh_artifacts()
        if cols[2].button("Dry Run", key=f"dry_{job.get('job_name')}"):
            st.session_state[f"manual_job_{job.get('job_name')}"] = api_post(f"/system/scheduler/run-job/{job.get('job_name')}", {"dry_run": True})
            refresh_artifacts()
        enabled_label = "Disable" if job.get("enabled") else "Enable"
        if cols[3].button(enabled_label, key=f"toggle_{job.get('job_name')}"):
            api_post(f"/system/scheduler/{job.get('job_name')}/enabled", {"enabled": not bool(job.get("enabled"))})
            refresh_artifacts()

    st.markdown("**Latest Job Runs**")
    st.dataframe(pd.DataFrame(scheduler_status.get("latest_by_job", [])), use_container_width=True)

    st.markdown("**Failed Jobs**")
    st.dataframe(pd.DataFrame(scheduler_status.get("failed_jobs", [])), use_container_width=True)

    latest_by_job = scheduler_status.get("latest_by_job", [])
    def latest_for(name: str) -> str:
        for row in latest_by_job:
            if row.get("job_name") == name:
                return row.get("finished_at") or row.get("started_at") or "never"
        return "never"

    cols = st.columns(4)
    cols[0].metric("Last Ingestion", latest_for("daily_price_ingestion"))
    cols[1].metric("Last Outcome Eval", latest_for("horizon_based_outcome_evaluation"))
    cols[2].metric("Last Calibration", latest_for("monthly_calibration_report"))
    cols[3].metric("Failed Jobs", len(scheduler_status.get("failed_jobs", [])))

    st.markdown("**Data Freshness Warnings**")
    if latest_for("daily_price_ingestion") == "never":
        st.warning("Daily price ingestion has not run yet.")
    if latest_for("horizon_based_outcome_evaluation") == "never":
        st.warning("Outcome evaluation has not run yet.")

    st.subheader("Fine-Tuning Readiness")
    st.json(st.session_state.get("readiness", {}))

    st.subheader("Institutional Readiness")
    st.json(st.session_state.get("institutional_readiness", {}))

    st.subheader("Lessons Learned")
    st.json(st.session_state.get("lessons", {}))

with tabs[8]:
    st.subheader("Historical Backtests")
    backtests = st.session_state.get("backtests", [])
    replay_dates = [row.get("available_replay_date") for row in backtests]
    st.write({"available_historical_replay_dates": replay_dates})
    st.dataframe(pd.DataFrame(backtests), use_container_width=True)
    if backtests:
        selected_date = st.selectbox("Replay date", replay_dates)
        selected = backtests[replay_dates.index(selected_date)]
        cols = st.columns(3)
        cols[0].metric("Hit/Miss", selected.get("hit_miss", "unknown"))
        cols[1].metric("Hedge Payoff", selected.get("realized_hedge_payoff", 0))
        cols[2].write(", ".join(selected.get("regime_labels", [])))
        st.markdown("**Predicted Thesis**")
        st.write(selected.get("predicted_thesis"))
        st.markdown("**Predicted Opportunities**")
        st.write(selected.get("predicted_opportunities"))
        st.markdown("**Predicted Hedges**")
        st.write(selected.get("predicted_hedges"))
        st.markdown("**Realized Returns**")
        st.dataframe(pd.DataFrame(selected.get("realized_returns", [])), use_container_width=True)
        st.markdown("**Post-Mortem**")
        st.json({
            "what_went_right": selected.get("what_went_right"),
            "what_went_wrong": selected.get("what_went_wrong"),
            "evidence_overweighted": selected.get("evidence_overweighted"),
            "evidence_missed": selected.get("evidence_missed"),
        })

with tabs[9]:
    st.subheader("Historical HCP Reports")
    uploaded_history = st.file_uploader("Upload historical report", type=["txt", "md", "eml", "pdf", "docx"], key="historical_upload")
    with st.form("historical_metadata_form"):
        hist_title = st.text_input("Document title", value="")
        hist_author = st.text_input("Author", value="")
        hist_date = st.text_input("Original publication date", value="")
        hist_type = st.selectbox("Report type", ["macro_report", "investment_committee", "hcp_report", "email_export"])
        hist_source = st.text_input("Original source", value="")
        approve_on_import = st.checkbox("Approve and index on import", value=False)
        import_submitted = st.form_submit_button("Import Historical Report")
    if uploaded_history is not None:
        preview_text = uploaded_history.getvalue()[:4000]
        st.markdown("**Document Preview**")
        try:
            st.text(preview_text.decode("utf-8", errors="ignore"))
        except AttributeError:
            st.text(str(preview_text))
    if import_submitted and uploaded_history is not None:
        upload_dir = ROOT / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / uploaded_history.name
        path.write_bytes(uploaded_history.getvalue())
        payload = {
            "path": str(path),
            "approve": approve_on_import,
            "metadata": {
                "title": hist_title or uploaded_history.name,
                "author": hist_author or None,
                "publication_date": hist_date or None,
                "report_type": hist_type,
                "original_source": hist_source or uploaded_history.name,
            },
        }
        st.session_state.import_result = api_post("/institutional/import", payload)
        refresh_artifacts()
    if st.session_state.get("import_result"):
        st.success(f"Imported document: {st.session_state.import_result.get('document_id')}")
        st.markdown("**Extracted Metadata Preview**")
        st.json({
            key: st.session_state.import_result.get(key)
            for key in ["title", "author", "publication_date", "report_type", "original_source", "parser_status", "ingestion_status"]
        })
        st.markdown("**Parsed Thesis Preview**")
        st.json(st.session_state.import_result.get("structured", {}))

    docs = st.session_state.get("institutional_documents", [])
    st.markdown("**Institutional Memory Status**")
    st.dataframe(pd.DataFrame(docs), use_container_width=True)
    if docs:
        labels = [f"{doc.get('document_id')} | {doc.get('title')}" for doc in docs]
        selected_doc_label = st.selectbox("Historical document", labels)
        selected_doc = docs[labels.index(selected_doc_label)]
        cols = st.columns(3)
        if cols[0].button("Approve & Index", key="approve_historical_doc"):
            st.session_state.approve_doc_result = api_post(f"/institutional/documents/{selected_doc['document_id']}/approve")
            refresh_artifacts()
        if cols[1].button("Link Historical Outcome", key="link_historical_doc"):
            st.session_state.link_doc_result = api_post(f"/institutional/documents/{selected_doc['document_id']}/link-outcome")
            refresh_artifacts()
        cols[2].metric("Outcome Linked", "yes" if selected_doc.get("outcome_linked") else "no")
        st.markdown("**Editable Parsed Fields**")
        st.info("Edit/save support is intentionally pending; current phase supports preview, approval, indexing, and outcome linking.")
        st.json(selected_doc.get("structured", {}))

    st.subheader("Historical Outcome Links")
    st.dataframe(pd.DataFrame(st.session_state.get("historical_postmortems", [])), use_container_width=True)

    st.subheader("Investment Committee Reports")
    reports = st.session_state.get("ic_reports", [])
    st.dataframe(pd.DataFrame([{k: v for k, v in row.items() if k != "markdown"} for row in reports]), use_container_width=True)
    if reports:
        selected_report = st.selectbox("Committee report", [row.get("run_id") for row in reports])
        report = reports[[row.get("run_id") for row in reports].index(selected_report)]
        st.markdown(report.get("markdown", ""))

with tabs[10]:
    st.subheader("Scenario Lab")
    lab = st.session_state.get("scenario_lab", {})
    cols = st.columns(4)
    cols[0].metric("Sequences", len(lab.get("sequences", [])))
    cols[1].metric("Phases", len(lab.get("phases", [])))
    cols[2].metric("Frozen Recommendations", len(lab.get("recommendations", [])))
    cols[3].metric("Post-Mortems", len(lab.get("postmortems", [])))

    st.markdown("**Scenario Builder**")
    with st.form("scenario_builder_form"):
        sequence_name = st.text_input("Scenario sequence", value="Inflation Surprise To Fed Overtightening")
        sequence_description = st.text_area("Sequence description", value="Scenario sequence tracking inflation surprise, Fed catch-up, and overtightening risk.")
        phase_number = st.number_input("Phase number", min_value=1, max_value=12, value=1)
        scenario_name = st.text_input("Scenario name", value="Inflation surprises higher while growth remains strong")
        scenario_date = st.text_input("Scenario date", value="2026-07-19")
        c1, c2, c3 = st.columns(3)
        growth_direction = c1.selectbox("Growth direction", ["strong", "slowing", "contracting", "mixed"])
        inflation_direction = c2.selectbox("Inflation direction", ["rising", "elevated", "falling", "stable", "mixed"])
        inflation_surprise = c3.selectbox("Inflation surprise", ["higher", "lower", "modest", "none"])
        c1, c2, c3 = st.columns(3)
        policy_stance = c1.selectbox("Central bank stance", ["delayed_tightening", "tightening", "aggressive_tightening", "restrictive", "easing"])
        policy_path = c2.text_input("Expected policy path", value="gradual_then_faster")
        curve_position = c3.selectbox("Central bank curve position", ["ahead", "behind", "neutral"])
        c1, c2, c3 = st.columns(3)
        labor = c1.selectbox("Labor-market conditions", ["tight", "firm", "mixed", "weakening"])
        financial = c2.selectbox("Financial conditions", ["easy", "tightening", "tight", "mixed"])
        fiscal = c3.selectbox("Fiscal conditions", ["expansionary", "neutral", "constrained"])
        c1, c2, c3 = st.columns(3)
        recession_probability = c1.slider("Recession probability", 0.0, 1.0, 0.25, 0.05)
        probability = c2.slider("Scenario probability", 0.0, 1.0, 0.55, 0.05)
        conviction = c3.slider("Conviction", 0.0, 10.0, 7.0, 0.5)
        duration = st.text_input("Scenario duration", value="6-12 months")
        invalidation = st.text_area("Invalidation triggers", value="Inflation rolls over quickly\nLabor market weakens abruptly")
        submitted_scenario = st.form_submit_button("Save Scenario Phase")
    if submitted_scenario:
        sequence = api_post("/scenario-lab/sequences", {"name": sequence_name, "description": sequence_description})
        scenario_payload = {
            "scenario_name": scenario_name,
            "scenario_date": scenario_date,
            "growth_direction": growth_direction,
            "inflation_direction": inflation_direction,
            "inflation_surprise": inflation_surprise,
            "central_bank_policy_stance": policy_stance,
            "expected_policy_path": policy_path,
            "central_bank_curve_position": curve_position,
            "labor_market_conditions": labor,
            "financial_conditions": financial,
            "fiscal_conditions": fiscal,
            "recession_probability": recession_probability,
            "scenario_duration": duration,
            "probability": probability,
            "conviction": conviction,
            "invalidation_triggers": [row.strip() for row in invalidation.splitlines() if row.strip()],
        }
        st.session_state.saved_scenario_phase = api_post(
            "/scenario-lab/phases",
            {"sequence_id": sequence["sequence_id"], "phase_number": int(phase_number), "scenario": scenario_payload},
        )
        refresh_artifacts()

    st.markdown("**Phase Timeline**")
    phases = lab.get("phases", [])
    phase_rows = [
        {
            "phase_id": row.get("phase_id"),
            "sequence_id": row.get("sequence_id"),
            "phase_number": row.get("phase_number"),
            "scenario_name": row.get("scenario", {}).get("scenario_name"),
            "scenario_date": row.get("scenario", {}).get("scenario_date"),
            "probability": row.get("scenario", {}).get("probability"),
            "conviction": row.get("scenario", {}).get("conviction"),
        }
        for row in phases
    ]
    st.dataframe(pd.DataFrame(phase_rows), use_container_width=True)
    if phases:
        phase_labels = [f"{row.get('phase_id')} | {row.get('scenario', {}).get('scenario_name')}" for row in phases]
        selected_phase_label = st.selectbox("Scenario phase", phase_labels)
        selected_phase = phases[phase_labels.index(selected_phase_label)]
        cols = st.columns(3)
        if cols[0].button("Run Historical Analogs", key="run_scenario_analogs"):
            st.session_state.scenario_analog_result = api_post(f"/scenario-lab/phases/{selected_phase['phase_id']}/analogs")
            refresh_artifacts()
        if cols[1].button("Generate Recommendations", key="run_scenario_recs"):
            st.session_state.scenario_rec_result = api_post(f"/scenario-lab/phases/{selected_phase['phase_id']}/recommendations")
            refresh_artifacts()
        if cols[2].button("Generate Post-Mortem", key="run_scenario_postmortem"):
            st.session_state.scenario_postmortem_result = api_post(f"/scenario-lab/phases/{selected_phase['phase_id']}/postmortem")
            refresh_artifacts()
        st.markdown("**Editable Macro Assumptions**")
        st.json(selected_phase.get("scenario", {}))

    st.markdown("**Ranked Historical Analogs**")
    analog_payloads = [row.get("payload", {}) for row in lab.get("analogs", [])]
    analog_rows = []
    cross_asset_rows = []
    for payload in analog_payloads:
        for analog in payload.get("ranked_historical_analogs", []):
            analog_rows.append({"phase_id": payload.get("phase_id"), **analog})
    if st.session_state.get("scenario_analog_result"):
        for analog in st.session_state.scenario_analog_result.get("ranked_historical_analogs", []):
            analog_rows.append({"phase_id": st.session_state.scenario_analog_result.get("phase_id"), **analog})
        cross_asset_rows = st.session_state.scenario_analog_result.get("cross_asset_performance", {}).get("summary", [])
    st.dataframe(pd.DataFrame(analog_rows), use_container_width=True)

    st.markdown("**Analog Comparison Table / Cross-Asset Return Heat Map**")
    if cross_asset_rows:
        heat_df = pd.DataFrame(cross_asset_rows)
    else:
        heat_df = pd.DataFrame()
    st.dataframe(heat_df, use_container_width=True)

    st.markdown("**Current Recommendations**")
    rec_rows = []
    for row in lab.get("recommendations", []):
        rec = row.get("recommendation", {})
        rec_rows.append({
            "recommendation_id": row.get("recommendation_id"),
            "phase_id": row.get("phase_id"),
            "asset_or_trade": rec.get("asset_or_trade"),
            "direction": rec.get("direction"),
            "category": rec.get("category"),
            "probability": rec.get("probability_of_success"),
            "conviction": rec.get("conviction"),
            "expected_return_range": rec.get("expected_return_range"),
            "invalidation": rec.get("invalidation_condition"),
        })
    st.dataframe(pd.DataFrame(rec_rows), use_container_width=True)
    if st.session_state.get("scenario_rec_result"):
        st.markdown("**Recommendation Buckets**")
        st.json(st.session_state.scenario_rec_result)

    st.markdown("**Scenario Comparison Matrix**")
    st.dataframe(pd.DataFrame(lab.get("comparison_matrix", [])), use_container_width=True)

    st.markdown("**Recommendation Tracker / Realized Performance**")
    st.dataframe(pd.DataFrame(lab.get("evaluations", [])), use_container_width=True)

    st.markdown("**Post-Mortem Viewer**")
    st.dataframe(pd.DataFrame(lab.get("postmortems", [])), use_container_width=True)
    if st.session_state.get("scenario_postmortem_result"):
        st.json(st.session_state.scenario_postmortem_result)

    st.markdown("**Scenario Lessons Learned**")
    st.json(st.session_state.get("lessons", {}))
