from app.models import AgentFinding, AgentInput, AgentOutput, HedgeIdea

SYSTEM_PROMPT = """
You are the Risk & Hedge Agent. Challenge the thesis, identify hidden exposures,
and propose asymmetric hedges that protect against bear/tail outcomes without
fully neutralizing the base-case portfolio.
"""


class RiskHedgeAgentInput(AgentInput):
    """Input schema for the Risk & Hedge Agent."""


class RiskHedgeAgentOutput(AgentOutput):
    """Output schema for the Risk & Hedge Agent."""


class RiskHedgeAgent:
    name = "Risk & Hedge Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: RiskHedgeAgentInput) -> RiskHedgeAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus RiskHedgeAgentInput.
        hedges = [
            HedgeIdea(
                name="Equity index put spread financed with upside call overwrite",
                asset_class="equity",
                rationale="Protects against a disorderly growth scare while preserving moderate upside participation.",
                asymmetry="Defined premium outlay and convex payoff if the bear/tail case accelerates.",
                thesis_fit="Hedges the main failure mode of the equity opportunity set.",
                catalyst="Growth data deteriorates faster than earnings expectations.",
                evidence=["Bear/tail case probability is non-trivial", "Credit and labor triggers could reprice quickly"],
                trigger="Initiate when equity volatility is cheap versus macro event risk.",
                risks=["Premium decay", "Upside overwrite can cap gains"],
                confirming_data=["Rising jobless claims", "Wider credit spreads", "Cheap implied volatility"],
                invalidating_data=["Volatility already expensive", "Earnings breadth improves materially"],
                conviction_score=7.1,
            ),
            HedgeIdea(
                name="Long gold or gold-call structure",
                asset_class="commodity",
                rationale="Hedges real-rate declines, policy credibility shocks, and geopolitical stress.",
                asymmetry="Limited downside if sized as options; upside in multiple adverse regimes.",
                thesis_fit="Complements duration and protects against policy credibility risk.",
                catalyst="Real yields fall or market concerns about policy credibility rise.",
                evidence=["Gold opportunity also appears in commodity review", "Useful against policy mistake risk"],
                trigger="Add on real-yield breakout lower or renewed inflation credibility concerns.",
                risks=["Higher real yields", "Stronger USD", "Option premium decay"],
                confirming_data=["Falling real yields", "Higher volatility in policy expectations"],
                invalidating_data=["Real yields rise and USD strengthens together"],
                conviction_score=7.0,
            ),
        ]
        return RiskHedgeAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[AgentFinding(title="Primary hedge menu created", summary="Two asymmetric hedge templates selected.", evidence=[h.name for h in hedges], confidence=0.64)],
            hedges=hedges,
        )
