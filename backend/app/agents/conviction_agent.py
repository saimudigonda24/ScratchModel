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


class ConvictionAgent:
    name = "Conviction Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: ConvictionAgentInput) -> ConvictionAgentOutput:
        # Future LLM/ranking model call goes here.
        opportunities: list[Opportunity] = agent_input.context.get("opportunities", [])
        ranked = sorted(opportunities, key=lambda item: item.conviction_score, reverse=True)
        avg_score = mean([item.conviction_score for item in ranked]) if ranked else 0.0
        return ConvictionAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[
                AgentFinding(
                    title="Cross-asset conviction ranking complete",
                    summary=f"Ranked {len(ranked)} opportunities. Average conviction score: {avg_score:.1f}/10.",
                    evidence=[item.name for item in ranked[:5]],
                    confidence=min(avg_score / 10, 1),
                )
            ],
            opportunities=ranked,
        )
