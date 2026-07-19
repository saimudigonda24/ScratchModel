import pytest
from pydantic import ValidationError

from app.agents.conviction_agent import ConvictionAgent, ConvictionAgentInput, ConvictionScoreValidationError
from app.models import Opportunity


def make_input(opportunities: list[Opportunity]) -> ConvictionAgentInput:
    return ConvictionAgentInput(
        macro_snapshot={"signals": [], "source_status": {}},
        human_report={"title": "test", "content": "test"},
        context={"opportunities": opportunities},
    )


def opp(name: str, score: float) -> Opportunity:
    return Opportunity(
        asset_class="equity",
        name=name,
        thesis=f"{name} thesis",
        probability_band="50-60%",
        conviction_score=score,
        evidence=["test evidence"],
    )


def invalid_opp(name: str, score) -> Opportunity:
    return Opportunity.model_construct(
        asset_class="equity",
        name=name,
        thesis=f"{name} thesis",
        probability_band="50-60%",
        conviction_score=score,
        evidence=["test evidence"],
        risks=[],
        confirming_data=[],
        invalidating_data=[],
        triggers=[],
        human_approval_status="pending",
    )


@pytest.fixture
def agent() -> ConvictionAgent:
    return ConvictionAgent()


def test_ranks_descending(agent):
    out = agent.run(make_input([opp("A", 3.0), opp("C", 9.0), opp("B", 6.0)]))
    assert [item.name for item in out.opportunities] == ["C", "B", "A"]


def test_deterministic(agent):
    items = [opp("A", 5.0), opp("B", 5.0), opp("C", 5.0)]
    first = [item.name for item in agent.run(make_input(items)).opportunities]
    second = [item.name for item in agent.run(make_input(items)).opportunities]
    assert first == second


def test_all_ties_preserve_input_order(agent):
    out = agent.run(make_input([opp("A", 7.0), opp("B", 7.0), opp("C", 7.0)]))
    assert [item.name for item in out.opportunities] == ["A", "B", "C"]


def test_empty_list(agent):
    out = agent.run(make_input([]))
    assert out.opportunities == []
    assert out.findings[0].confidence == 0.0
    assert "Ranked 0 opportunities" in out.findings[0].summary


def test_missing_context_key(agent):
    empty_input = ConvictionAgentInput(
        macro_snapshot={"signals": [], "source_status": {}},
        human_report={"title": "test", "content": "test"},
        context={},
    )
    assert agent.run(empty_input).opportunities == []


def test_single_opportunity(agent):
    out = agent.run(make_input([opp("A", 8.0)]))
    assert [item.name for item in out.opportunities] == ["A"]
    assert out.findings[0].confidence == pytest.approx(0.8)


def test_evidence_is_top_five(agent):
    out = agent.run(make_input([opp(f"N{i}", float(i)) for i in range(10)]))
    assert out.findings[0].evidence == ["N9", "N8", "N7", "N6", "N5"]


def test_evidence_shorter_than_five(agent):
    out = agent.run(make_input([opp("A", 1.0), opp("B", 2.0)]))
    assert out.findings[0].evidence == ["B", "A"]


def test_confidence_clamped_above(agent):
    out = agent.run(make_input([opp("A", 10.0)]))
    with pytest.raises(ConvictionScoreValidationError):
        agent.run(make_input([invalid_opp("A", 50.0)]))
    assert out.findings[0].confidence == 1.0


def test_confidence_clamped_below_schema_rejects_public_negative_scores():
    with pytest.raises(ValidationError):
        opp("A", -5.0)


def test_agent_rejects_negative_scores_if_schema_is_bypassed(agent):
    with pytest.raises(ConvictionScoreValidationError, match="between 0 and 10"):
        agent.run(make_input([invalid_opp("A", -5.0)]))


def test_nan_score_rejected(agent):
    with pytest.raises(ConvictionScoreValidationError, match="non-finite"):
        agent.run(make_input([invalid_opp("A", float("nan")), opp("B", 5.0)]))


def test_infinite_score_rejected(agent):
    with pytest.raises(ConvictionScoreValidationError, match="non-finite"):
        agent.run(make_input([invalid_opp("A", float("inf")), opp("B", 5.0)]))


def test_none_score_raises_domain_error(agent):
    with pytest.raises(ConvictionScoreValidationError, match="missing"):
        agent.run(make_input([invalid_opp("A", None), opp("B", 5.0)]))


@pytest.mark.xfail(
    strict=True,
    reason="Future feature. Confidence currently means average pick conviction, not ranking dispersion. "
    "Recommended design: add a separate rank_confidence or dispersion metric rather than overloading finding confidence.",
)
def test_confidence_tracks_dispersion(agent):
    ambiguous = agent.run(make_input([opp(letter, 8.0) for letter in "ABCD"]))
    decisive = agent.run(make_input([opp("A", 9.0), opp("B", 3.0), opp("C", 2.0), opp("D", 1.0)]))
    assert decisive.findings[0].confidence > ambiguous.findings[0].confidence


def test_summary_count(agent):
    out = agent.run(make_input([opp(f"N{i}", float(i)) for i in range(7)]))
    assert "Ranked 7 opportunities" in out.findings[0].summary


def test_system_prompt_stripped(agent):
    assert agent.system_prompt
    assert agent.system_prompt == agent.system_prompt.strip()


def test_output_identity(agent):
    out = agent.run(make_input([opp("A", 1.0)]))
    assert out.agent_name == "Conviction Agent"
    assert out.system_prompt == agent.system_prompt


def test_input_is_not_mutated(agent):
    items = [opp("A", 1.0), opp("B", 9.0)]
    agent.run(make_input(items))
    assert [item.name for item in items] == ["A", "B"]


@pytest.mark.xfail(
    strict=True,
    reason="Future feature. Crowding is not part of the Opportunity schema yet. Recommended design: add optional "
    "crowding_score and/or positioning_risk fields before ranking penalties consume it.",
)
def test_crowding_is_penalized():
    agent = ConvictionAgent()
    crowded = opp("CROWDED", 8.0)
    contrarian = opp("CONTRARIAN", 8.0)
    crowded.crowding = 0.95  # type: ignore[attr-defined]
    contrarian.crowding = 0.10  # type: ignore[attr-defined]
    out = agent.run(make_input([crowded, contrarian]))
    assert [item.name for item in out.opportunities] == ["CONTRARIAN", "CROWDED"]
