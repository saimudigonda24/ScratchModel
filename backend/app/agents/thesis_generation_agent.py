from app.models import AgentFinding, AgentInput, AgentOutput, CaseView, MacroThesis

SYSTEM_PROMPT = """
You are the Thesis Generation Agent for HCP. Synthesize machine-readable macro
signals and human HCP research into a living 7-14 month macro thesis. Express
base, bull, and bear/tail cases with probabilities, evidence, and invalidation
triggers.
"""


class ThesisGenerationAgentInput(AgentInput):
    """Input schema for the Thesis Generation Agent."""


class ThesisGenerationAgentOutput(AgentOutput):
    """Output schema for the Thesis Generation Agent."""


class ThesisGenerationAgent:
    name = "Thesis Generation Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: ThesisGenerationAgentInput) -> ThesisGenerationAgentOutput:
        # Future LLM call goes here. Pass SYSTEM_PROMPT plus ThesisGenerationAgentInput.
        text = agent_input.human_report.content.lower()
        inflation_bias = "inflation" in text or "rates" in text
        growth_signals = [s for s in agent_input.macro_snapshot.signals if s.direction in {"improving", "mixed"}]
        risk_signals = [s for s in agent_input.macro_snapshot.signals if s.direction == "deteriorating"]

        thesis = MacroThesis(
            title="Disinflation With Slower Growth and Policy Optionality",
            base_case=CaseView(
                label="base",
                summary="Growth cools but avoids a deep recession, inflation trends lower unevenly, and policy becomes more supportive over the forecast horizon.",
                probability=0.55,
                evidence=[s.interpretation for s in growth_signals[:3]],
            ),
            bull_case=CaseView(
                label="bull",
                summary="Productivity and easing financial conditions extend the cycle, supporting risk assets and selective cyclicals.",
                probability=0.25,
                evidence=["Labor remains resilient", "Credit spreads stay contained", "Earnings revisions stabilize"],
            ),
            bear_tail_case=CaseView(
                label="bear_tail",
                summary="Sticky inflation or a credit shock forces tighter real rates and a defensive cross-asset regime.",
                probability=0.20,
                evidence=[s.interpretation for s in risk_signals[:3]] or ["Policy mistake risk remains non-zero"],
            ),
            key_signals=agent_input.macro_snapshot.signals[:8],
            triggers=[
                "Core inflation re-accelerates for two consecutive releases",
                "Unemployment rises more than 75 bps from current levels",
                "Credit spreads widen materially without a growth rebound",
                "Forward EPS revisions turn broadly negative",
            ],
            change_log=[
                "Initial mock thesis created from HCP report text and free-source macro signal placeholders.",
                "Report text explicitly references inflation/rates." if inflation_bias else "Report text did not heavily reference inflation/rates.",
            ],
        )
        agent_input.context["thesis"] = thesis
        return ThesisGenerationAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[
                AgentFinding(
                    title=thesis.title,
                    summary=thesis.base_case.summary,
                    evidence=thesis.base_case.evidence,
                    confidence=thesis.base_case.probability,
                )
            ],
            notes=["MacroThesis object attached to workflow context."],
        )
