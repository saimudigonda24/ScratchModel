from collections import defaultdict
from dataclasses import dataclass


@dataclass
class CalibrationSummary:
    brier_score: float
    calibration_buckets: dict[str, dict[str, float]]
    overconfidence_score: float
    underconfidence_score: float


def brier_score(probability: float, actual: int) -> float:
    return (probability - actual) ** 2


def bucket_probability(probability: float) -> str:
    lower = int(probability * 10) * 10
    upper = min(lower + 10, 100)
    return f"{lower}-{upper}%"


def summarize_calibration(forecasts: list[dict]) -> CalibrationSummary:
    if not forecasts:
        return CalibrationSummary(0.0, {}, 0.0, 0.0)
    briers = [brier_score(item["probability"], item["actual_outcome"]) for item in forecasts]
    grouped = defaultdict(list)
    for item in forecasts:
        grouped[bucket_probability(item["probability"])].append(item)
    buckets = {}
    over = []
    under = []
    for bucket, rows in grouped.items():
        avg_prob = sum(row["probability"] for row in rows) / len(rows)
        hit_rate = sum(row["actual_outcome"] for row in rows) / len(rows)
        gap = avg_prob - hit_rate
        if gap > 0:
            over.append(gap)
        else:
            under.append(abs(gap))
        buckets[bucket] = {"count": len(rows), "avg_probability": avg_prob, "hit_rate": hit_rate, "gap": gap}
    return CalibrationSummary(
        brier_score=sum(briers) / len(briers),
        calibration_buckets=buckets,
        overconfidence_score=sum(over) / len(over) if over else 0.0,
        underconfidence_score=sum(under) / len(under) if under else 0.0,
    )

