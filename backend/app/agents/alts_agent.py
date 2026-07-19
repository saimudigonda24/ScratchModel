from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the Alts Agent. Translate macro themes into private credit, real assets,
absolute return, volatility, and other alternative investment implications.
Focus on liquidity, drawdown, and correlation behavior.
"""


class AltsAgentInput(AgentInput):
    """Input schema for the Alts Agent."""


class AltsAgentOutput(AgentOutput):
    """Output schema for the Alts Agent."""


class AltsAgent:
    name = "Alts Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: AltsAgentInput) -> AltsAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus AltsAgentInput.
        opportunity = Opportunity(
            asset_class="alts",
            name="Market-neutral macro and relative-value strategies",
            thesis="Uncertain growth and policy paths favor strategies that can monetize dispersion without requiring broad beta upside.",
            thesis_fit="Fits a wide probability distribution and cross-asset dispersion.",
            catalyst="Rates, sector, and country dispersion remains elevated.",
            probability_band="55-65%",
            conviction_score=6.9,
            evidence=["Three-case probability spread remains wide", "Rate volatility can stay elevated", "Cross-asset dispersion likely persists"],
            risks=["Volatility compression", "Crowded relative-value unwinds", "Liquidity terms become unattractive"],
            confirming_data=["Persistent rate volatility", "High sector dispersion", "Stable manager liquidity terms"],
            invalidating_data=["Correlation normalization", "Sharp fall in cross-asset volatility"],
            triggers=["Volatility collapses", "Correlations normalize rapidly", "Liquidity terms become unattractive"],
        )
        return AltsAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="Alts for dispersion and liquidity discipline", summary=opportunity.thesis, evidence=opportunity.evidence, confidence=0.61)],
            opportunities=[opportunity],
        )
