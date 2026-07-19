from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the Fixed Income Agent. Identify duration, curve, credit, and inflation
linked opportunities implied by the macro thesis. Separate carry, convexity,
and recession hedge characteristics.
"""


class FixedIncomeAgentInput(AgentInput):
    """Input schema for the Fixed Income Agent."""


class FixedIncomeAgentOutput(AgentOutput):
    """Output schema for the Fixed Income Agent."""


class FixedIncomeAgent:
    name = "Fixed Income Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: FixedIncomeAgentInput) -> FixedIncomeAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus FixedIncomeAgentInput.
        opportunity = Opportunity(
            asset_class="fixed_income",
            name="Intermediate duration with curve steepener optionality",
            thesis="If growth slows and policy optionality rises, intermediate duration offers carry plus upside from lower front-end rate expectations.",
            thesis_fit="Best aligned with disinflation, slower growth, and a more two-sided central bank reaction function.",
            catalyst="Softer inflation and labor data pull forward rate-cut expectations.",
            probability_band="55-65%",
            conviction_score=7.8,
            evidence=["CME FedWatch signal points to easier policy odds", "Disinflation base case", "Bear case still benefits from flight-to-quality"],
            risks=["Inflation re-acceleration", "Term premium shock", "Heavy supply repricing"],
            confirming_data=["Lower core inflation", "Higher continuing claims", "Dovish central bank communication"],
            invalidating_data=["Upside inflation surprises", "Curve bear steepening on fiscal concerns"],
            triggers=["Inflation re-accelerates", "Term premium shock", "Fiscal supply overwhelms duration demand"],
        )
        return FixedIncomeAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="Duration as thesis-aligned ballast", summary=opportunity.thesis, evidence=opportunity.evidence, confidence=0.66)],
            opportunities=[opportunity],
        )
