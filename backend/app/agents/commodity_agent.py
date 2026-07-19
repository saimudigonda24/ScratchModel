from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the Commodity Agent. Map macro, inventory, policy, and geopolitical
signals into energy, metals, and agricultural opportunities. Prioritize
asymmetric supply-demand setups.
"""


class CommodityAgentInput(AgentInput):
    """Input schema for the Commodity Agent."""


class CommodityAgentOutput(AgentOutput):
    """Output schema for the Commodity Agent."""


class CommodityAgent:
    name = "Commodity Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: CommodityAgentInput) -> CommodityAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus CommodityAgentInput.
        opportunity = Opportunity(
            asset_class="commodity",
            name="Gold as real-rate and tail-risk convexity",
            thesis="Gold can participate if real yields fall in the base case and hedge if policy credibility or geopolitical risk deteriorates.",
            thesis_fit="Fits both the base case of lower real-rate pressure and bear/tail policy credibility risk.",
            catalyst="Real yields decline or geopolitical/policy risk rises.",
            probability_band="50-60%",
            conviction_score=7.0,
            evidence=["Disinflation plus easier policy path", "Bear/tail case includes policy mistake risk", "Cross-asset hedge value"],
            risks=["Real yields rise sharply", "USD rallies", "Liquidity stress creates broad selling"],
            confirming_data=["Lower real yields", "Higher central bank demand", "Rising geopolitical risk premium"],
            invalidating_data=["Sustained rise in real yields", "Breakdown below technical support"],
            triggers=["Real yields rise sharply", "USD breakout", "Liquidity stress forces broad asset liquidation"],
        )
        return CommodityAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="Gold retains asymmetric role", summary=opportunity.thesis, evidence=opportunity.evidence, confidence=0.60)],
            opportunities=[opportunity],
        )
