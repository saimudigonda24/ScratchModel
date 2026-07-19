import math
from statistics import mean

from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the Conviction Agent. Compare all asset-class recommendations, penalize
weak evidence and crowded or one-way assumptions, then rank opportunities by
probability, payoff asymmetry, evidence quality, and trigger clarity.
"""


class ConvictionAgentInput(AgentInput):
    """Input schema for the Conviction Agent."""


class ConvictionAgentOutput(AgentOutput):
    """Output schema for the Conviction Agent."""


class ConvictionScoreValidationError(ValueError):
    """Raised when an opportunity carries an invalid conviction score."""


class ConvictionAgent:
    name = "Conviction Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: ConvictionAgentInput) -> ConvictionAgentOutput:
        # Future LLM/ranking model call goes here.
        opportunities: list[Opportunity] = agent_input.context.get("opportunities", [])
        for item in opportunities:
            self._validate_conviction_score(item)
        ranked = sorted(opportunities, key=lambda item: item.conviction_score, reverse=True)
        avg_score = mean([item.conviction_score for item in ranked]) if ranked else 0.0
        confidence = max(0.0, min(avg_score / 10, 1.0))
        return ConvictionAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[
                AgentFinding(
                    title="Cross-asset conviction ranking complete",
                    summary=f"Ranked {len(ranked)} opportunities. Average conviction score: {avg_score:.1f}/10.",
                    evidence=[item.name for item in ranked[:5]],
                    confidence=confidence,
                )
            ],
            opportunities=ranked,
        )

    def _validate_conviction_score(self, item: Opportunity) -> None:
        score = item.conviction_score
        if score is None:
            raise ConvictionScoreValidationError(f"{item.name} has missing conviction_score")
        if not isinstance(score, (int, float)):
            raise ConvictionScoreValidationError(f"{item.name} has non-numeric conviction_score: {score!r}")
        if not math.isfinite(float(score)):
            raise ConvictionScoreValidationError(f"{item.name} has non-finite conviction_score: {score!r}")
        if not 0 <= float(score) <= 10:
            raise ConvictionScoreValidationError(f"{item.name} conviction_score must be between 0 and 10: {score!r}")
