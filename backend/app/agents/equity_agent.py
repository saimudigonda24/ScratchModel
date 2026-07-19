from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the Equity Agent. Translate the HCP macro thesis into public equity,
sector, factor, and thematic opportunities. Favor 7-14 month setups with clear
evidence, asymmetry, and thesis-change triggers.
"""


class EquityAgentInput(AgentInput):
    """Input schema for the Equity Agent."""


class EquityAgentOutput(AgentOutput):
    """Output schema for the Equity Agent."""


class EquityAgent:
    name = "Equity Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: EquityAgentInput) -> EquityAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus EquityAgentInput.
        opportunity = Opportunity(
            asset_class="equity",
            name="Quality cyclicals with pricing power",
            thesis="A soft-landing base case supports companies with operating leverage while slower nominal growth punishes weak balance sheets.",
            thesis_fit="Fits a base case of slower but positive growth and disinflation.",
            catalyst="Forward earnings revisions stabilize while inflation data continues to moderate.",
            probability_band="50-60%",
            conviction_score=7.2,
            evidence=["Base case avoids deep recession", "Inflation moderation can support margins", "Earnings revisions are a key trigger"],
            risks=["Hard landing compresses multiples", "Margins disappoint if demand weakens faster than costs"],
            confirming_data=["Positive EPS revisions", "Stable credit spreads", "Improving new orders"],
            invalidating_data=["Two months of broad negative revisions", "Sharp credit spread widening"],
            triggers=["ISM new orders contract sharply", "Credit spreads break higher", "EPS revisions roll over"],
        )
        return EquityAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="Equity barbell favored", summary=opportunity.thesis, evidence=opportunity.evidence, confidence=0.62)],
            opportunities=[opportunity],
        )
