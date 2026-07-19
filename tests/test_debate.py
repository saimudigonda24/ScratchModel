import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.connectors import ingest_all_sources
from app.models import CaseView, MacroThesis, Opportunity
from app.services.model_debate import run_model_debate


def test_model_debate_uses_three_provider_slots(monkeypatch):
    monkeypatch.setenv("HCP_USE_REAL_DATA", "false")
    monkeypatch.setenv("HCP_USE_REAL_LLM", "false")
    thesis = MacroThesis(
        title="Test thesis",
        base_case=CaseView(label="base", summary="Slower growth and lower inflation.", probability=0.55, evidence=[]),
        bull_case=CaseView(label="bull", summary="Growth re-accelerates.", probability=0.25, evidence=[]),
        bear_tail_case=CaseView(label="bear_tail", summary="Credit stress rises.", probability=0.20, evidence=[]),
        key_signals=[],
        triggers=[],
        change_log=[],
    )
    opportunity = Opportunity(
        asset_class="fixed_income",
        name="Duration",
        thesis="Rates fall if growth slows.",
        probability_band="55-65%",
        conviction_score=7.5,
        evidence=["Mock evidence"],
    )

    debate = run_model_debate(thesis, ingest_all_sources(), [opportunity])

    assert len(debate.raw_answers) == 9
    assert len(debate.debate_rounds) == 4
    assert debate.agreements
    assert debate.final_ranked_ideas
    assert debate.human_review_questions
