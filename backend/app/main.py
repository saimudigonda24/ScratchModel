import json
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.connectors import ingest_all_sources
from app.models import FinalResearchOutput, MacroDataSnapshot, WorkflowRequest
from app.services.database import (
    approved_training_examples,
    init_db,
    list_approval_queue,
    list_approval_queue_detailed,
    list_regime_labels,
    list_lessons_learned,
    list_institutional_documents,
    list_debates,
    outcome_summary,
    save_proxy_override,
    list_reports,
    list_thesis_versions,
    update_approval,
)
from app.services.automated_outcome_evaluator import AutomatedOutcomeEvaluator
from app.services.historical_outcome_linker import link_historical_outcome, list_linked_historical_outcomes
from app.services.institutional_importer import approve_and_index_document, import_historical_document
from app.services.institutional_readiness import institutional_readiness_report
from app.services.investment_committee_report import list_committee_reports
from app.services.price_ingestion import PriceIngestionService
from app.services.calibration_report import generate_calibration_report, latest_calibration_report
from app.services.fine_tuning_readiness import fine_tuning_readiness_report
from app.services.eval_ranking import evaluate_outcome_rankings
from app.services.scheduler import LightweightScheduler
from app.services.backtesting import HistoricalBacktestService
from app.services.institutional_memory import dashboard_lessons_summary, generate_lessons_learned
from app.services.proxy_mapping import all_proxy_mappings
from app.services.regime_labeling import RegimeInput, save_run_regime_label
from app.services.scenario_lab import (
    create_demo_three_phase_sequence,
    create_or_update_scenario_sequence,
    cross_asset_historical_performance,
    generate_phase_postmortem,
    generate_scenario_recommendations,
    identify_historical_analogs,
    save_phase,
    scenario_comparison_matrix,
    scenario_lab_dashboard_data,
)
from app.services import run_research_workflow
from app.services.storage import write_jsonl

ROOT = Path(__file__).resolve().parents[2]

app = FastAPI(
    title="HCP Macro Theme AI Investment System",
    description="AI-powered macro investing research platform prototype. Research only; no order execution.",
    version="0.1.0",
)

init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "v1-functional"}


@app.get("/signals", response_model=MacroDataSnapshot)
def get_signals() -> MacroDataSnapshot:
    return ingest_all_sources()


@app.post("/workflow/run", response_model=FinalResearchOutput)
def run_workflow(request: WorkflowRequest) -> FinalResearchOutput:
    return run_research_workflow(report_text=request.report_text, report_title=request.report_title)


@app.post("/workflow/upload-text", response_model=FinalResearchOutput)
async def upload_report_text(report_text: str = Body(..., media_type="text/plain")) -> FinalResearchOutput:
    return run_research_workflow(report_text=report_text, report_title="Uploaded HCP report text")


@app.get("/artifacts/training-examples")
def list_training_examples() -> list[dict]:
    rows: list[dict] = []
    for path in sorted((ROOT / "datasets" / "cleaned_examples").glob("*.jsonl"))[-10:]:
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                row["_path"] = str(path)
                rows.append(row)
    return rows


@app.get("/artifacts/evaluations")
def list_evaluations() -> list[dict]:
    rows: list[dict] = []
    for path in sorted((ROOT / "reports" / "evaluations").glob("*.json"))[-10:]:
        row = json.loads(path.read_text())
        row["_path"] = str(path)
        rows.append(row)
    return rows


@app.get("/history/reports")
def report_history() -> list[dict]:
    return list_reports()


@app.get("/history/thesis")
def thesis_history() -> list[dict]:
    return list_thesis_versions()


@app.get("/history/debates")
def debate_history() -> list[dict]:
    return list_debates()


@app.get("/approvals")
def approval_queue() -> list[dict]:
    return list_approval_queue_detailed()


@app.post("/approvals/{approval_id}/{status}")
def set_approval_status(approval_id: int, status: str) -> dict:
    try:
        return update_approval(approval_id, status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/training/export-approved")
def export_approved_training_examples() -> dict:
    rows = approved_training_examples()
    path = ROOT / "datasets" / "jsonl" / "approved_hcp_training_examples.jsonl"
    write_jsonl(path, rows)
    return {"count": len(rows), "path": str(path)}


@app.get("/outcomes")
def outcomes() -> dict:
    return outcome_summary()


@app.get("/outcomes/conviction-ranking-evaluation")
def conviction_ranking_evaluation() -> dict:
    return evaluate_outcome_rankings()


@app.get("/outcomes/proxy-mappings")
def proxy_mappings() -> list[dict]:
    return all_proxy_mappings()


@app.post("/outcomes/export-evaluation-dataset")
def export_evaluation_dataset() -> dict:
    data = outcome_summary()
    rows = data.get("opportunity_outcomes", []) + data.get("hedge_outcomes", [])
    path = ROOT / "datasets" / "jsonl" / "hcp_outcome_evaluation_dataset.jsonl"
    write_jsonl(path, rows)
    return {"count": len(rows), "path": str(path)}


@app.post("/outcomes/proxy-override")
def proxy_override(payload: dict) -> dict:
    return save_proxy_override(payload)


@app.post("/outcomes/ingest-prices")
def ingest_prices(payload: dict) -> dict:
    tickers = payload.get("tickers", [])
    if isinstance(tickers, str):
        tickers = [ticker.strip() for ticker in tickers.split(",") if ticker.strip()]
    return PriceIngestionService().ingest_prices(tickers, payload["start_date"], payload["end_date"])


@app.post("/outcomes/evaluate")
def evaluate_outcomes(payload: dict | None = None) -> dict:
    return AutomatedOutcomeEvaluator().evaluate(as_of=(payload or {}).get("as_of"))


@app.get("/system/scheduler")
def scheduler_status() -> dict:
    return LightweightScheduler().status_summary()


@app.post("/system/scheduler/run")
def run_scheduler(payload: dict | None = None) -> list[dict]:
    return LightweightScheduler().run_once(dry_run=(payload or {}).get("dry_run", False))


@app.post("/system/scheduler/run-job/{job_name}")
def run_scheduler_job(job_name: str, payload: dict | None = None) -> dict:
    return LightweightScheduler().run_job(job_name, dry_run=(payload or {}).get("dry_run", False))


@app.post("/system/scheduler/{job_name}/enabled")
def set_scheduler_job_enabled(job_name: str, payload: dict) -> dict:
    try:
        return LightweightScheduler().set_job_enabled(job_name, bool(payload.get("enabled")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/outcomes/generate-calibration-report")
def create_calibration_report() -> dict:
    return generate_calibration_report()


@app.get("/outcomes/latest-calibration-report")
def get_latest_calibration_report() -> dict | None:
    return latest_calibration_report()


@app.get("/training/fine-tuning-readiness")
def readiness_report() -> dict:
    return fine_tuning_readiness_report()


@app.get("/institutional/readiness")
def institutional_readiness() -> dict:
    return institutional_readiness_report()


@app.get("/institutional/documents")
def institutional_documents() -> list[dict]:
    return list_institutional_documents()


@app.post("/institutional/import")
def import_institutional_document(payload: dict) -> dict:
    try:
        return import_historical_document(Path(payload["path"]), metadata=payload.get("metadata", {}), approve=payload.get("approve", False))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/institutional/documents/{document_id}/approve")
def approve_document(document_id: str) -> dict:
    return approve_and_index_document(document_id)


@app.post("/institutional/documents/{document_id}/link-outcome")
def link_document_outcome(document_id: str) -> dict:
    try:
        return link_historical_outcome(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/institutional/postmortems")
def historical_postmortems() -> list[dict]:
    return list_linked_historical_outcomes()


@app.get("/investment-committee/reports")
def investment_committee_reports() -> list[dict]:
    return list_committee_reports()


@app.get("/regimes")
def regimes() -> list[dict]:
    return list_regime_labels()


@app.post("/regimes/label")
def create_regime_label(payload: dict) -> dict:
    metrics = RegimeInput(**payload.get("metrics", {}))
    return save_run_regime_label(
        payload["run_id"],
        payload["period_start"],
        metrics,
        payload.get("period_end"),
    )


@app.get("/backtests/historical")
def historical_backtests() -> list[dict]:
    return HistoricalBacktestService().dashboard_summaries()


@app.post("/backtests/run-standard-suite")
def run_historical_backtests() -> list[dict]:
    HistoricalBacktestService().run_standard_suite()
    return HistoricalBacktestService().dashboard_summaries()


@app.get("/memory/lessons")
def lessons_learned() -> dict:
    return dashboard_lessons_summary()


@app.post("/memory/generate-lessons")
def create_lessons_learned() -> dict:
    return generate_lessons_learned()


@app.get("/scenario-lab")
def scenario_lab() -> dict:
    return scenario_lab_dashboard_data()


@app.post("/scenario-lab/demo")
def scenario_lab_demo() -> dict:
    return create_demo_three_phase_sequence()


@app.post("/scenario-lab/sequences")
def create_scenario_sequence(payload: dict) -> dict:
    return create_or_update_scenario_sequence(payload["name"], payload.get("description", ""), payload.get("sequence_id"))


@app.post("/scenario-lab/phases")
def create_scenario_phase(payload: dict) -> dict:
    return save_phase(payload["sequence_id"], int(payload["phase_number"]), payload["scenario"], payload.get("data_snapshot"))


@app.post("/scenario-lab/phases/{phase_id}/analogs")
def run_scenario_analogs(phase_id: str) -> dict:
    from app.services.database import get_scenario_phase

    phase = get_scenario_phase(phase_id)
    if not phase:
        raise HTTPException(status_code=404, detail="Scenario phase not found")
    analogs = identify_historical_analogs(phase)
    return {**analogs, "cross_asset_performance": cross_asset_historical_performance(analogs["ranked_historical_analogs"])}


@app.post("/scenario-lab/phases/{phase_id}/recommendations")
def run_scenario_recommendations(phase_id: str) -> dict:
    from app.services.database import get_scenario_phase

    phase = get_scenario_phase(phase_id)
    if not phase:
        raise HTTPException(status_code=404, detail="Scenario phase not found")
    analogs = identify_historical_analogs(phase)
    return generate_scenario_recommendations(phase, analogs)


@app.post("/scenario-lab/phases/{phase_id}/postmortem")
def create_scenario_postmortem(phase_id: str) -> dict:
    return generate_phase_postmortem(phase_id)


@app.get("/scenario-lab/comparison")
def compare_scenarios() -> dict:
    return scenario_comparison_matrix()
