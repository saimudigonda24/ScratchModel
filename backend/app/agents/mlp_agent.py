from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the MLP Agent. Evaluate midstream energy infrastructure and MLPs through
cash-flow durability, rates, commodity sensitivity, tax considerations, and
income quality. Research only; no order execution.
"""


class MLPAgentInput(AgentInput):
    """Input schema for the MLP Agent."""


class MLPAgentOutput(AgentOutput):
    """Output schema for the MLP Agent."""


class MLPAgent:
    name = "MLP Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: MLPAgentInput) -> MLPAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus MLPAgentInput.
        opportunity = Opportunity(
            asset_class="mlp",
            name="Midstream income with inflation-linked cash-flow resilience",
            thesis="MLPs can offer income and infrastructure exposure if growth slows but energy demand remains stable.",
            thesis_fit="Fits a slower-growth environment where cash yield and hard-asset exposure matter.",
            catalyst="Stable energy volumes and easing rate pressure improve income-asset relative appeal.",
            probability_band="45-55%",
            conviction_score=6.2,
            evidence=["Cash-flow durability can matter in slower growth", "Rate pressure may ease in base case"],
            risks=["Energy demand shock", "Rate backup", "Tax complexity and idiosyncratic leverage"],
            confirming_data=["Stable pipeline volumes", "Contained credit spreads", "Lower rate volatility"],
            invalidating_data=["Oil demand collapse", "Distribution coverage deterioration"],
            triggers=["Energy demand weakens", "Credit spreads widen", "Rates back up sharply"],
        )
        return MLPAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="MLPs as income-sensitive real assets", summary=opportunity.thesis, evidence=opportunity.evidence, confidence=0.53)],
            opportunities=[opportunity],
        )

