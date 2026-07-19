from app.models import AgentFinding, AgentInput, AgentOutput, EvaluationResult

SYSTEM_PROMPT = """
You are the Evaluation Agent. Score completed research outputs for reasoning
accuracy, thesis consistency, evidence quality, risk analysis, hedge quality,
and usefulness. Scores are rubric estimates until real human labels exist.
"""


class EvaluationAgentInput(AgentInput):
    """Input schema for the Evaluation Agent."""


class EvaluationAgentOutput(AgentOutput):
    evaluation_result: EvaluationResult | None = None


class EvaluationAgent:
    name = "Evaluation Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: EvaluationAgentInput) -> EvaluationAgentOutput:
        # Future LLM or human-label comparison call goes here.
        opportunities = agent_input.context.get("opportunities", [])
        hedges = agent_input.context.get("hedges", [])
        result = EvaluationResult(
            reasoning_quality=7.3,
            macro_consistency=7.8 if opportunities else 5.0,
            evidence_quality=6.8,
            cross_asset_reasoning=7.5 if len(opportunities) >= 5 else 5.5,
            risk_awareness=7.1,
            hedge_quality=7.0 if hedges else 4.0,
            clarity=7.4,
            actionability=7.2,
            notes=[
                "Mock rubric score only; replace with human labels and realized outcome tracking.",
                "Evidence quality should improve once live data connectors and citations are added.",
            ],
        )
        agent_input.context["evaluation_result"] = result
        return EvaluationAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[
                AgentFinding(
                    title="Evaluation rubric complete",
                    summary="Scored output against the initial HCP research-quality rubric.",
                    evidence=result.notes,
                    confidence=0.7,
                )
            ],
            evaluation_result=result,
        )
