import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import run_research_workflow


def test_workflow_returns_required_sections(monkeypatch):
    monkeypatch.setenv("HCP_USE_REAL_DATA", "false")
    monkeypatch.setenv("HCP_USE_REAL_LLM", "false")
    result = run_research_workflow("Inflation, rates, growth, and hedges matter for HCP.")

    assert result.thesis.base_case.label == "base"
    assert result.thesis.bull_case.label == "bull"
    assert result.thesis.bear_tail_case.label == "bear_tail"
    assert 0 <= result.conviction_score <= 10
    assert result.ranked_opportunities
    assert result.asymmetric_hedges
    assert result.ranked_hedge_ideas
    assert result.debate_notes
    assert result.human_approval_queue
    assert result.training_examples
    assert result.evaluation_result
    assert result.model_debate
    assert len(result.model_debate.raw_answers) == 9
    assert result.saved_output_path
    assert result.saved_training_path
    assert "Research hypotheses for human review only" in result.disclaimer
    assert result.saved_output_path
    run_id = Path(result.saved_output_path).stem
    assert (ROOT / "data" / "snapshots" / f"{run_id}_combined.json").exists()
