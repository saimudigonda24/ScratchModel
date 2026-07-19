import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.services.database import list_approval_queue, list_reports
from scripts.create_sample_macro_report import create_report
from scripts.run_hcp_analysis_from_report import run_from_report


def test_run_hcp_analysis_from_report_creates_pending_run(tmp_path, monkeypatch):
    monkeypatch.setenv("HCP_USE_REAL_DATA", "false")
    monkeypatch.setenv("HCP_USE_REAL_LLM", "false")
    report_path = tmp_path / "sample_macro_report.md"
    create_report(report_path)

    run_id = run_from_report(report_path)

    reports = [row for row in list_reports(20) if row["run_id"] == run_id]
    approvals = [row for row in list_approval_queue(500) if row["run_id"] == run_id]
    assert reports
    assert reports[0]["training_approved"] == 0
    assert approvals
    assert all(row["approval_status"] == "pending" for row in approvals)

