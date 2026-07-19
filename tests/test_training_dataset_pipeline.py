import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from training.build_training_dataset import build_examples_from_runs, write_jsonl
from training.validate_training_dataset import validate_dataset, validate_examples


def _approved_run():
    opportunity = {
        "asset_class": "equity",
        "name": "Quality cyclicals",
        "thesis": "Research hypothesis.",
        "evidence": ["earnings revisions"],
        "risks": ["hard landing"],
        "confirming_data": ["positive EPS revisions"],
        "invalidating_data": ["credit spreads widen"],
        "human_approval_status": "pending",
    }
    hedge = {
        "asset_class": "commodity",
        "name": "Gold calls",
        "evidence": ["real yields"],
        "risks": ["premium decay"],
    }
    return {
        "run_id": "run_1",
        "report_title": "HCP report",
        "human_report": "Human macro view.",
        "created_at": "2026-06-29T00:00:00",
        "macro_data_snapshot": {"signals": [{"source": "FRED", "name": "10Y", "value": "4%"}]},
        "research_output": {
            "thesis": {
                "base_case": {"summary": "base"},
                "bull_case": {"summary": "bull"},
                "bear_tail_case": {"summary": "bear"},
            },
            "probability_bands": {"base_case": "55%"},
            "ranked_opportunities": [opportunity],
            "ranked_hedge_ideas": [hedge],
            "evidence": ["macro evidence"],
        },
        "quality_scores": {"actionability": 7.2},
        "outcome_evaluated": True,
        "eligible_for_fine_tuning": True,
    }


def test_build_training_examples_are_supervised_and_approved(tmp_path):
    examples = build_examples_from_runs([_approved_run()])
    output_path = write_jsonl(examples, tmp_path / "hcp_macro_training.jsonl")

    ok, errors = validate_dataset(output_path)

    assert ok, errors
    row = json.loads(output_path.read_text())
    assert row["input"]["macro_data_snapshot"]
    assert row["input"]["human_report"]
    assert row["output"]["approved_opportunities"]
    assert row["metadata"]["approval_status"] == "approved"


def test_validator_rejects_unapproved_and_missing_risks():
    examples = build_examples_from_runs([_approved_run()])
    examples[0]["metadata"]["approval_status"] = "pending"
    examples[0]["output"]["ranked_opportunities"][0]["risks"] = []

    errors = validate_examples(examples)

    assert any("unapproved" in error for error in errors)
    assert any("empty risks" in error for error in errors)
