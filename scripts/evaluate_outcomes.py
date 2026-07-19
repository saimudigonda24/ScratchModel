import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.automated_outcome_evaluator import AutomatedOutcomeEvaluator  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()
    print(AutomatedOutcomeEvaluator().evaluate(as_of=args.as_of))


if __name__ == "__main__":
    main()

