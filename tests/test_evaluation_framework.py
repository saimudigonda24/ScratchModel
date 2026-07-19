import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from evals.evaluation_framework import score_output


def test_evaluation_framework_scores_requested_dimensions():
    result = score_output(
        {
            "ranked_opportunities": [{"evidence": ["a"], "risks": ["b"]} for _ in range(5)],
            "ranked_hedge_ideas": [{"name": "hedge"}],
        }
    )

    scores = result["scores"]
    assert "reasoning_quality" in scores
    assert "macro_consistency" in scores
    assert "cross_asset_reasoning" in scores
    assert "actionability" in scores
