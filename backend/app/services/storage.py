import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[3]
REPORTS_RAW = ROOT / "reports" / "raw"
REPORTS_OUTPUTS = ROOT / "reports" / "outputs"
REPORTS_EVALUATIONS = ROOT / "reports" / "evaluations"
CLEANED_EXAMPLES = ROOT / "datasets" / "cleaned_examples"
DATA_SNAPSHOTS = ROOT / "data" / "snapshots"


def timestamp_id(prefix: str) -> str:
    return f"{prefix}_{datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}"


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default))
    return path


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, default=_json_default) for row in rows) + "\n")
    return path


def save_raw_report(content: str, title: str, run_id: str) -> Path:
    safe_title = "".join(char if char.isalnum() else "_" for char in title).strip("_")[:60] or "report"
    path = REPORTS_RAW / f"{run_id}_{safe_title}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def save_research_output(payload: dict[str, Any], run_id: str) -> Path:
    return write_json(REPORTS_OUTPUTS / f"{run_id}.json", payload)


def save_evaluation(payload: dict[str, Any], run_id: str) -> Path:
    return write_json(REPORTS_EVALUATIONS / f"{run_id}.json", payload)


def save_training_examples(rows: list[dict[str, Any]], run_id: str) -> Path:
    return write_jsonl(CLEANED_EXAMPLES / f"{run_id}.jsonl", rows)


def save_data_snapshots(snapshot: Any, run_id: str) -> list[Path]:
    payload = snapshot.model_dump(mode="json") if isinstance(snapshot, BaseModel) else snapshot
    paths: list[Path] = []
    combined_path = write_json(DATA_SNAPSHOTS / f"{run_id}_combined.json", payload)
    paths.append(combined_path)

    signals = payload.get("signals", [])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for signal in signals:
        grouped.setdefault(signal["source"], []).append(signal)
    for source, source_signals in grouped.items():
        safe_source = "".join(char.lower() if char.isalnum() else "_" for char in source).strip("_")
        paths.append(
            write_json(
                DATA_SNAPSHOTS / f"{run_id}_{safe_source}.json",
                {
                    "run_id": run_id,
                    "source": source,
                    "signals": source_signals,
                    "source_status": payload.get("source_status", {}).get(source),
                    "generated_at": payload.get("generated_at"),
                },
            )
        )
    return paths
