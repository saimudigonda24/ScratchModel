from app.models import AgentFinding, AgentInput, AgentOutput

SYSTEM_PROMPT = """
You are the Debate Judge Agent. Simulate a multi-model investment committee by
recording pro, con, and judge notes. Stress-test assumptions, surface missing
evidence, and decide whether the final output should be promoted, revised, or
held for more data.
"""


class DebateJudgeAgentInput(AgentInput):
    """Input schema for the Debate Judge Agent."""


class DebateJudgeAgentOutput(AgentOutput):
    """Output schema for the Debate Judge Agent."""


class DebateJudgeAgent:
    name = "Debate Judge Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: DebateJudgeAgentInput) -> DebateJudgeAgentOutput:
        # Future multi-model debate call goes here.
        model_debate = agent_input.context.get("model_debate")
        if model_debate:
            notes = [
                f"Agreements: {'; '.join(model_debate.agreements)}",
                f"Disagreements: {'; '.join(model_debate.disagreements)}",
                f"Hidden risks: {'; '.join(model_debate.hidden_risks)}",
                f"Final ranked ideas: {'; '.join(model_debate.final_ranked_ideas)}",
                model_debate.judge_summary,
            ]
            return DebateJudgeAgentOutput(
                agent_name=self.name,
                system_prompt=self.system_prompt,
                findings=[
                    AgentFinding(
                        title="Model debate judged",
                        summary=model_debate.judge_summary,
                        evidence=notes,
                        confidence=0.72,
                    )
                ],
                notes=notes,
            )
        notes = [
            "Pro model: base case is internally consistent with softer inflation and policy optionality.",
            "Skeptic model: thesis depends on labor cooling without credit stress; monitor unemployment and spreads closely.",
            "Judge: publish as provisional research output with explicit triggers and hedge menu.",
        ]
        return DebateJudgeAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[
                AgentFinding(
                    title="Debate placeholder complete",
                    summary="The thesis is publishable as decision support, with risk controls and trigger monitoring.",
                    evidence=notes,
                    confidence=0.68,
                )
            ],
            notes=notes,
        )
