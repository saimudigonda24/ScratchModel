from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the FX/Rates Agent. Convert relative growth, inflation, and policy paths
into currency and rates views. Emphasize cross-market confirmation and regime
break triggers.
"""


class FXRatesAgentInput(AgentInput):
    """Input schema for the FX/Rates Agent."""


class FXRatesAgentOutput(AgentOutput):
    """Output schema for the FX/Rates Agent."""


class FXRatesAgent:
    name = "FX/Rates Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: FXRatesAgentInput) -> FXRatesAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus FXRatesAgentInput.
        opportunity = Opportunity(
            asset_class="fx_rates",
            name="Selective USD downside versus higher-real-yield peers",
            thesis="A Fed pivot path and less exceptional U.S. growth can reduce dollar support if global risk appetite remains stable.",
            thesis_fit="Fits a thesis where U.S. policy exceptionalism fades but global growth does not collapse.",
            catalyst="Relative real-rate differentials move against the dollar.",
            probability_band="45-55%",
            conviction_score=6.4,
            evidence=["Policy optionality rises", "Global activity signals are mixed rather than collapsing", "USD remains sensitive to real-rate differentials"],
            risks=["Risk-off dollar squeeze", "U.S. growth re-accelerates", "Foreign central banks ease first"],
            confirming_data=["Narrower U.S. real-rate advantage", "Stable global PMIs"],
            invalidating_data=["Dollar breakout", "Global stress indicators spike"],
            triggers=["U.S. growth re-accelerates", "Global risk-off shock", "Foreign central banks turn more dovish first"],
        )
        return FXRatesAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="Dollar exceptionalism watch", summary=opportunity.thesis, evidence=opportunity.evidence, confidence=0.54)],
            opportunities=[opportunity],
        )
