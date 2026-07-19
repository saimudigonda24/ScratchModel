import json
from datetime import datetime
from pathlib import Path

from app.services.database import outcome_summary
from app.services.forecast_calibration import summarize_calibration

ROOT = Path(__file__).resolve().parents[3]
CALIBRATION_DIR = ROOT / "reports" / "calibration"


def generate_calibration_report() -> dict:
    summary = outcome_summary()
    forecasts = [
        {"probability": row["probability"], "actual_outcome": row["actual_outcome"]}
        for row in summary.get("forecast_outcomes", [])
        if row.get("actual_outcome") is not None
    ]
    calibration = summarize_calibration(forecasts)
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "hit_rate_by_asset_class": summary.get("hit_rate_by_asset_class", {}),
        "hit_rate": summary.get("hit_rate", 0.0),
        "average_return_by_conviction_bucket": summary.get("average_return_by_conviction_bucket", {}),
        "brier_score": calibration.brier_score,
        "calibration_buckets": calibration.calibration_buckets,
        "overconfidence": calibration.overconfidence_score,
        "underconfidence": calibration.underconfidence_score,
        "best_recommendations": summary.get("best_recommendations", []),
        "worst_recommendations": summary.get("worst_recommendations", []),
        "recurring_failure_modes": infer_failure_modes(summary),
        "what_model_tends_to_miss": infer_missed_patterns(summary),
    }
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    path = CALIBRATION_DIR / f"calibration_{datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    report["path"] = str(path)
    return report


def latest_calibration_report() -> dict | None:
    paths = sorted(CALIBRATION_DIR.glob("calibration_*.json"))
    if not paths:
        return None
    payload = json.loads(paths[-1].read_text())
    payload["path"] = str(paths[-1])
    return payload


def infer_failure_modes(summary: dict) -> list[str]:
    worst = summary.get("worst_recommendations", [])
    modes = []
    if any((row.get("max_drawdown") or 0) < -0.1 for row in worst):
        modes.append("Drawdown risk was underestimated.")
    if any(row.get("hit_miss_label") == "miss" for row in worst):
        modes.append("Directional conviction failed in some high-ranked ideas.")
    return modes or ["Insufficient evaluated history to infer recurring failure modes."]


def infer_missed_patterns(summary: dict) -> list[str]:
    if not summary.get("forecast_outcomes"):
        return ["Forecast calibration history is too sparse."]
    return ["Review probability buckets with persistent overconfidence or underconfidence."]

