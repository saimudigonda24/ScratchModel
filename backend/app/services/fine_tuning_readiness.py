from collections import Counter

from app.services.calibration_report import latest_calibration_report
from app.services.database import list_outcome_dashboard_data
from app.services.quality_gates import readiness_gate_explanation
from app.services.regime_labeling import regime_coverage_summary


def fine_tuning_readiness_report(minimum_examples: int = 100) -> dict:
    data = list_outcome_dashboard_data()
    opportunity_outcomes = data.get("opportunity_outcomes", [])
    regime_coverage = regime_coverage_summary()
    eligible = [
        row
        for row in opportunity_outcomes
        if row.get("eligible_for_fine_tuning") and regime_coverage
    ]
    evaluated = [row for row in opportunity_outcomes if row.get("outcome_evaluated")]
    asset_counts = Counter(row.get("asset_class") for row in eligible)
    quality_scores = [row.get("outcome_quality_score") for row in eligible if row.get("outcome_quality_score") is not None]
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    calibration = latest_calibration_report() or {}
    remaining = max(0, minimum_examples - len(eligible))
    if len(eligible) >= minimum_examples and avg_quality >= 7:
        recommendation = "ready"
    elif len(eligible) >= minimum_examples * 0.5 and avg_quality >= 6.5:
        recommendation = "nearly ready"
    else:
        recommendation = "not ready"
    return {
        "total_approved_examples": len(opportunity_outcomes),
        "total_outcome_evaluated_examples": len(evaluated),
        "total_eligible_examples": len(eligible),
        "asset_class_coverage": dict(asset_counts),
        "regime_coverage": regime_coverage,
        "average_quality_score": avg_quality,
        "calibration_quality": calibration.get("brier_score"),
        "minimum_recommended_examples_still_needed": remaining,
        "recommendation": recommendation,
        "quality_gate_explanation": readiness_gate_explanation(),
    }
