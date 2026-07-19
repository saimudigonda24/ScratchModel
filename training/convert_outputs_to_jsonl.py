"""Convert saved HCP research outputs into JSONL training examples."""

import argparse
import json
from pathlib import Path
from typing import Any


def build_examples_from_output(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("training_examples"):
        return payload["training_examples"]

    return [
        {
            "example_id": payload.get("generated_at", "unknown"),
            "task": "macro_research_output",
            "input": {
                "source_status": payload.get("source_status", {}),
                "probability_bands": payload.get("probability_bands", {}),
            },
            "output": {
                "thesis": payload.get("thesis"),
                "ranked_opportunities": payload.get("ranked_opportunities", []),
                "ranked_hedge_ideas": payload.get("ranked_hedge_ideas", []),
                "human_approval_queue": payload.get("human_approval_queue", []),
            },
            "metadata": {
                "source": "saved_research_output",
                "requires_human_review": True,
            },
        }
    ]


def convert(input_dir: Path, output_path: Path) -> int:
    rows: list[dict[str, Any]] = []
    for path in sorted(input_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        rows.extend(build_examples_from_output(payload))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(json.dumps(row) for row in rows) + ("\n" if rows else ""))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="reports/outputs")
    parser.add_argument("--output", default="datasets/jsonl/hcp_training_examples.jsonl")
    args = parser.parse_args()
    count = convert(Path(args.input_dir), Path(args.output))
    print(f"Wrote {count} training examples to {args.output}")


if __name__ == "__main__":
    main()

