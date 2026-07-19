"""Run the full HCP analysis workflow from a human macro report file."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import run_research_workflow  # noqa: E402
from app.services.database import list_approval_queue  # noqa: E402


def run_from_report(report_path: Path) -> str:
    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")
    report_text = report_path.read_text()
    result = run_research_workflow(report_text=report_text, report_title=report_path.name)
    run_id = Path(result.saved_output_path or "").stem
    if not run_id:
        raise RuntimeError("Workflow did not save an output path")
    approvals = [item for item in list_approval_queue(limit=500) if item["run_id"] == run_id]
    print(f"Run ID: {run_id}")
    print(f"Saved output: {result.saved_output_path}")
    print(f"Human approval items created: {len(approvals)}")
    print("Next step: open Streamlit, review this run in the Approvals tab, and approve items before building the training dataset.")
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="Path to a human macro report under reports/raw")
    args = parser.parse_args()
    run_from_report(Path(args.report))


if __name__ == "__main__":
    main()

