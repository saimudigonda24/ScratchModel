import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.fine_tuning_readiness import fine_tuning_readiness_report  # noqa: E402


def main() -> None:
    print(json.dumps(fine_tuning_readiness_report(), indent=2))


if __name__ == "__main__":
    main()

