import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from training.convert_outputs_to_jsonl import convert


def test_training_conversion(tmp_path):
    input_dir = tmp_path / "outputs"
    input_dir.mkdir()
    (input_dir / "run.json").write_text(
        json.dumps(
            {
                "generated_at": "test",
                "training_examples": [
                    {
                        "example_id": "ex1",
                        "task": "test",
                        "input": {},
                        "output": {},
                        "metadata": {"approval_status": "pending"},
                    }
                ],
            }
        )
    )
    output_path = tmp_path / "examples.jsonl"

    count = convert(input_dir, output_path)

    assert count == 1
    assert output_path.read_text().strip()

