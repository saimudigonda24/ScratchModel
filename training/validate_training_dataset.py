"""Validate approved HCP supervised training dataset JSONL."""

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_DATASET = Path("datasets/cleaned_examples/hcp_macro_training.jsonl")


class ValidationError(Exception):
    pass


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _validate_opportunity(item: dict[str, Any], line_no: int, index: int, errors: list[str]) -> None:
    prefix = f"line {line_no} opportunity {index}"
    _require(bool(item.get("evidence")), f"{prefix}: missing evidence", errors)
    _require(bool(item.get("risks")), f"{prefix}: empty risks", errors)
    _require(bool(item.get("confirming_data")), f"{prefix}: missing confirming_data", errors)
    _require(bool(item.get("invalidating_data")), f"{prefix}: missing invalidating_data", errors)
    _require(
        item.get("human_approval_status", "pending") in {"pending", "approved", "rejected", "needs_revision"},
        f"{prefix}: invalid human_approval_status",
        errors,
    )


def validate_examples(examples: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    for line_no, example in enumerate(examples, start=1):
        example_id = example.get("example_id")
        _require(bool(example_id), f"line {line_no}: missing example_id", errors)
        if example_id:
            _require(example_id not in seen_ids, f"line {line_no}: duplicate example_id {example_id}", errors)
            seen_ids.add(example_id)

        _require(bool(example.get("input")), f"line {line_no}: missing input", errors)
        _require(bool(example.get("output")), f"line {line_no}: missing output", errors)
        metadata = example.get("metadata", {})
        _require(metadata.get("approval_status") == "approved", f"line {line_no}: unapproved example included", errors)
        _require(metadata.get("human_approved") is True, f"line {line_no}: missing human_approved=true", errors)
        _require(metadata.get("outcome_evaluated") is True, f"line {line_no}: missing outcome_evaluated=true", errors)
        _require(metadata.get("eligible_for_fine_tuning") is True, f"line {line_no}: missing eligible_for_fine_tuning=true", errors)
        _require(metadata.get("outcome_quality_score") is not None, f"line {line_no}: missing outcome_quality_score", errors)

        output = example.get("output", {})
        for key in [
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
            "approved_reasoning_format",
        ]:
            _require(key in output, f"line {line_no}: output missing {key}", errors)

        _require(bool(output.get("evidence")), f"line {line_no}: missing evidence fields", errors)
        _require(bool(output.get("risks")), f"line {line_no}: empty risks", errors)
        opportunities = output.get("ranked_opportunities") or []
        _require(bool(opportunities), f"line {line_no}: no ranked opportunities", errors)
        for index, item in enumerate(opportunities, start=1):
            _validate_opportunity(item, line_no, index, errors)

        hedges = output.get("approved_hedges") or []
        _require(bool(hedges), f"line {line_no}: no approved hedges", errors)
        for index, item in enumerate(hedges, start=1):
            _require(bool(item.get("evidence")), f"line {line_no} hedge {index}: missing evidence", errors)
            _require(bool(item.get("risks")), f"line {line_no} hedge {index}: empty risks", errors)

    return errors


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValidationError(f"Dataset not found: {path}")
    examples: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            examples.append(json.loads(line))
    return examples


def validate_dataset(path: Path = DEFAULT_DATASET) -> tuple[bool, list[str]]:
    errors = validate_examples(load_jsonl(path))
    return not errors, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    args = parser.parse_args()
    ok, errors = validate_dataset(Path(args.dataset))
    if not ok:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Validation passed for {args.dataset}")


if __name__ == "__main__":
    main()
