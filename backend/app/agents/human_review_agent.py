from pydantic import Field

from app.models import AgentFinding, AgentInput, AgentOutput, HumanReviewItem

SYSTEM_PROMPT = """
You are the Human Review Agent. Identify any thesis, opportunity, hedge, data
quality issue, or model disagreement requiring human approval before publication.
Never approve automatically.
"""


class HumanReviewAgentInput(AgentInput):
    """Input schema for the Human Review Agent."""


class HumanReviewAgentOutput(AgentOutput):
    review_items: list[HumanReviewItem] = Field(default_factory=list)


class HumanReviewAgent:
    name = "Human Review Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: HumanReviewAgentInput) -> HumanReviewAgentOutput:
        # Future LLM call goes here. Human approval should remain explicit.
        opportunities = agent_input.context.get("opportunities", [])
        hedges = agent_input.context.get("hedges", [])
        review_items = [
            HumanReviewItem(
                item_type="thesis",
                name=agent_input.thesis.title if agent_input.thesis else "Macro thesis",
                reason="Initial thesis requires human investment committee review before use.",
                priority="high",
            )
        ]
        for item in opportunities[:3]:
            review_items.append(
                HumanReviewItem(
                    item_type="opportunity",
                    name=item.name,
                    reason="Top-ranked opportunity requires human review for sizing, suitability, and evidence quality.",
                    priority="medium",
                )
            )
        for item in hedges[:2]:
            review_items.append(
                HumanReviewItem(
                    item_type="hedge",
                    name=item.name,
                    reason="Hedge structure requires review for cost, liquidity, and implementation constraints.",
                    priority="medium",
                )
            )
        agent_input.context["human_review_items"] = review_items
        return HumanReviewAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[
                AgentFinding(
                    title="Human approval queue created",
                    summary=f"Flagged {len(review_items)} items for human approval.",
                    evidence=[item.name for item in review_items],
                    confidence=0.9,
                )
            ],
            review_items=review_items,
        )
