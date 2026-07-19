import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import run_research_workflow
from app.services.database import list_approval_queue, list_reports, list_thesis_versions, update_approval


def test_database_save_load_and_approval_update(monkeypatch):
    monkeypatch.setenv("HCP_USE_REAL_DATA", "false")
    monkeypatch.setenv("HCP_USE_REAL_LLM", "false")
    run_research_workflow("Database test report on inflation, rates, and hedges.")

    assert list_reports()
    assert list_thesis_versions()
    approvals = list_approval_queue()
    assert approvals

    updated = update_approval(approvals[0]["id"], "approved")
    assert updated["approval_status"] == "approved"
