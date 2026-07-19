"""Build approved supervised JSONL examples for future HCP fine-tuning.

This script does not train a model. It converts approved workflow runs into
input/output pairs that teach the HCP macro reasoning and output framework.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.database import list_approved_training_runs  # noqa: E402

DEFAULT_OUTPUT = ROOT / "datasets" / "cleaned_examples" / "hcp_macro_training.jsonl"

TASK_INSTRUCTIONS = """
Use the macro data snapshot and human HCP macro report to produce an HCP-style
macro investment research output. Return a structured thesis with base, bull,
and bear/tail cases; ranked cross-asset research hypotheses; hedges; evidence;
risks; confirming data; invalidating data; and human-review status. This is a
research framework exercise only, not trading advice or order execution.
""".strip()


def _approved_output(research_output: dict[str, Any]) -> dict[str, Any]:
    opportunities = research_output.get("ranked_opportunities", [])
    hedges = research_output.get("ranked_hedge_ideas") or research_output.get("asymmetric_hedges", [])
    return {
        "macro_thesis": research_output.get("thesis"),
        "base_case": research_output.get("thesis", {}).get("base_case"),
        "bull_case": research_output.get("thesis", {}).get("bull_case"),
        "bear_tail_case": research_output.get("thesis", {}).get("bear_tail_case"),
        "probability_bands": research_output.get("probability_bands"),
        "ranked_opportunities": opportunities,
        "approved_opportunities": opportunities,
        "approved_hedges": hedges,
        "evidence": research_output.get("evidence", []),
        "risks": [risk for item in opportunities for risk in item.get("risks", [])],
        "confirming_data": [datum for item in opportunities for datum in item.get("confirming_data", [])],
        "invalidating_data": [datum for item in opportunities for datum in item.get("invalidating_data", [])],
        "approved_reasoning_format": {
            "required_sections": [
                "macro_thesis",
                "base_case",
                "bull_case",
                "bear_tail_case",
                "ranked_opportunities",
                "approved_hedges",
                "evidence",
                "risks",
                "confirming_data",
                "invalidating_data",
            ],
            "style": "HCP macro investment committee research hypothesis",
            "constraints": [
                "Research only",
                "No trade execution",
                "Human approval required",
                "Every idea must include evidence and risks",
            ],
        },
    }


def build_examples_from_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for run in runs:
        research_output = run["research_output"]
        examples.append(
            {
                "example_id": f"{run['run_id']}_approved_supervised",
                "task": "hcp_macro_research_supervised_output",
                "input": {
                    "macro_data_snapshot": run["macro_data_snapshot"],
                    "human_report": {
                        "title": run["report_title"],
                        "content": run["human_report"],
                    },
                    "task_instructions": TASK_INSTRUCTIONS,
                },
                "output": _approved_output(research_output),
                "metadata": {
                    "run_id": run["run_id"],
                    "created_at": run["created_at"],
                    "approval_status": "approved",
                    "human_approved": True,
                    "outcome_evaluated": run.get("outcome_evaluated", False),
                    "outcome_quality_score": run.get("quality_scores", {}).get("actionability"),
                    "eligible_for_fine_tuning": run.get("eligible_for_fine_tuning", False),
                    "source": "approved_hcp_workflow_run",
                    "training_goal": "Learn HCP reasoning and output format, not market prediction from raw data.",
                },
            }
        )
    return examples


def write_jsonl(examples: list[dict[str, Any]], output_path: Path = DEFAULT_OUTPUT) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(example) for example in examples)
    output_path.write_text(content + ("\n" if content else ""))
    return output_path


def build_dataset(output_path: Path = DEFAULT_OUTPUT) -> tuple[int, Path]:
    examples = build_examples_from_runs(list_approved_training_runs())
    path = write_jsonl(examples, output_path)
    return len(examples), path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    count, path = build_dataset(Path(args.output))
    print(f"Wrote {count} approved supervised training examples to {path}")


if __name__ == "__main__":
    main()
