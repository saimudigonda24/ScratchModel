"""Simple rubric evaluation for HCP research outputs."""

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class RubricScores:
    reasoning_quality: float
    macro_consistency: float
    evidence_quality: float
    cross_asset_reasoning: float
    risk_awareness: float
    hedge_quality: float
    clarity: float
    actionability: float


def score_output(payload: dict[str, Any]) -> dict[str, Any]:
    opportunities = payload.get("ranked_opportunities", [])
    hedges = payload.get("ranked_hedge_ideas") or payload.get("asymmetric_hedges", [])
    has_risks = all(item.get("risks") for item in opportunities) if opportunities else False
    has_evidence = all(item.get("evidence") for item in opportunities) if opportunities else False

    scores = RubricScores(
        reasoning_quality=7.0,
        macro_consistency=7.5 if opportunities else 4.0,
        evidence_quality=7.0 if has_evidence else 4.0,
        cross_asset_reasoning=7.5 if len(opportunities) >= 5 else 5.0,
        risk_awareness=7.0 if has_risks else 4.0,
        hedge_quality=7.0 if hedges else 3.0,
        clarity=7.0,
        actionability=7.0 if opportunities and hedges else 4.0,
    )
    return {
        "scores": asdict(scores),
        "notes": [
            "Initial rubric uses structural checks and placeholder scores.",
            "Replace with human labels, realized-outcome review, and model-vs-human comparisons.",
        ],
    }
