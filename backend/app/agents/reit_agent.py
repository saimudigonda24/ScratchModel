from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the REIT Agent. Evaluate listed real estate by property type, rates,
credit availability, balance-sheet strength, occupancy, and refinancing risk.
Separate income, duration, and distress-sensitive views.
"""


class REITAgentInput(AgentInput):
    """Input schema for the REIT Agent."""


class REITAgentOutput(AgentOutput):
    """Output schema for the REIT Agent."""


class REITAgent:
    name = "REIT Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: REITAgentInput) -> REITAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus REITAgentInput.
        opportunity = Opportunity(
            asset_class="reit",
            name="Selective REITs with strong balance sheets and secular demand",
            thesis="If rates stabilize, high-quality REITs in durable property types can recover while weaker refinancing stories remain vulnerable.",
            thesis_fit="Fits the base case of rate stabilization with slower but non-recessionary growth.",
            catalyst="Long rates stop rising and credit availability improves for quality issuers.",
            probability_band="45-55%",
            conviction_score=6.1,
            evidence=["Duration-sensitive assets can recover as rates stabilize", "Balance-sheet quality should matter"],
            risks=["Commercial real estate credit shock", "Higher cap rates", "Tenant demand deterioration"],
            confirming_data=["Lower long-rate volatility", "Stable occupancy", "Improving REIT credit spreads"],
            invalidating_data=["CRE delinquencies accelerate", "Refinancing spreads widen"],
            triggers=["10Y yields break higher", "CRE stress rises", "Occupancy weakens"],
        )
        return REITAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="REIT selectivity matters", summary=opportunity.thesis, evidence=opportunity.evidence, confidence=0.52)],
            opportunities=[opportunity],
        )

