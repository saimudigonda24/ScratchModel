from app.models import AgentFinding, AgentInput, AgentOutput, Opportunity

SYSTEM_PROMPT = """
You are the Crypto Agent. Evaluate crypto assets as macro-liquidity, real-rate,
risk appetite, and adoption-sensitive opportunities. Keep recommendations as
research hypotheses requiring human review.
"""


class CryptoAgentInput(AgentInput):
    """Input schema for the Crypto Agent."""


class CryptoAgentOutput(AgentOutput):
    """Output schema for the Crypto Agent."""


class CryptoAgent:
    name = "Crypto Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: CryptoAgentInput) -> CryptoAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus CryptoAgentInput.
        opportunity = Opportunity(
            asset_class="crypto",
            name="Small tactical allocation to liquid crypto beta",
            thesis="If real rates fall and liquidity expectations improve, liquid crypto beta can express upside convexity to easier financial conditions.",
            thesis_fit="Fits the bull case and liquidity-sensitive extension of the base case.",
            catalyst="Real yields decline while risk appetite broadens beyond mega-cap equities.",
            probability_band="40-50%",
            conviction_score=5.8,
            evidence=["Crypto remains sensitive to liquidity expectations", "Policy optionality could support speculative duration assets"],
            risks=["Regulatory shock", "Risk-off deleveraging", "Crypto-specific security or exchange event"],
            confirming_data=["Lower real yields", "Improving stablecoin liquidity", "Broad risk appetite"],
            invalidating_data=["Regulatory enforcement shock", "Liquidity stress", "Breakdown in major crypto market structure"],
            triggers=["Real yields rise", "Liquidity indicators deteriorate", "Regulatory headlines worsen"],
        )
        return CryptoAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="Crypto is convex but lower conviction", summary=opportunity.thesis, evidence=opportunity.evidence, confidence=0.48)],
            opportunities=[opportunity],
        )

