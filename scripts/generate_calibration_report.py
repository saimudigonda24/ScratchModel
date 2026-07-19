import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.calibration_report import generate_calibration_report  # noqa: E402


def main() -> None:
    report = generate_calibration_report()
    print(f"Generated calibration report: {report['path']}")


if __name__ == "__main__":
    main()

