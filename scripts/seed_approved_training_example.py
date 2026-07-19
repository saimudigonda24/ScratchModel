"""Create one fully approved workflow run for testing the training pipeline."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import run_research_workflow  # noqa: E402
from app.services.database import list_approval_queue, update_approval  # noqa: E402


SEED_REPORT = """
HCP seed macro report:

Over the next 7-14 months, U.S. growth is likely to slow but avoid a deep
recession if labor cooling remains orderly. Inflation should continue to
moderate unevenly, giving central banks a more two-sided reaction function.
The research process should compare equities, bonds, FX/rates, commodities,
crypto, MLPs, REITs, and alternatives, while explicitly identifying hedges,
risks, confirming data, and invalidating data.
"""


def seed() -> str:
    result = run_research_workflow(SEED_REPORT, report_title="Seed Approved HCP Training Example")
    run_id = Path(result.saved_output_path or "").stem
    if not run_id:
        raise RuntimeError("Workflow did not save an output path")

    approvals = [item for item in list_approval_queue(limit=500) if item["run_id"] == run_id]
    if not approvals:
        raise RuntimeError(f"No approval items found for {run_id}")
    for item in approvals:
        update_approval(item["id"], "approved")
    return run_id


def main() -> None:
    run_id = seed()
    print(f"Seeded approved workflow run: {run_id}")


if __name__ == "__main__":
    main()

