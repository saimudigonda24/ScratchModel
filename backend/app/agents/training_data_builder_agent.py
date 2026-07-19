from uuid import uuid4

from pydantic import Field

from app.models import AgentFinding, AgentInput, AgentOutput, TrainingExample

SYSTEM_PROMPT = """
You are the Training Data Builder Agent. Convert completed workflows into
future fine-tuning examples that teach the HCP macro-investing framework,
preferred output format, evidence standards, risk analysis, and thesis updates.
"""


class TrainingDataBuilderAgentInput(AgentInput):
    """Input schema for the Training Data Builder Agent."""


class TrainingDataBuilderAgentOutput(AgentOutput):
    training_examples: list[TrainingExample] = Field(default_factory=list)


class TrainingDataBuilderAgent:
    name = "Training Data Builder Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: TrainingDataBuilderAgentInput) -> TrainingDataBuilderAgentOutput:
        # Future LLM call can rewrite examples into provider-specific fine-tune formats.
        opportunities = agent_input.context.get("opportunities", [])
        hedges = agent_input.context.get("hedges", [])
        thesis = agent_input.thesis
        examples = [
            TrainingExample(
                example_id=str(uuid4()),
                task="macro_thesis_to_cross_asset_research",
                input={
                    "human_report": agent_input.human_report.content,
                    "signals": [signal.model_dump() for signal in agent_input.macro_snapshot.signals],
                },
                output={
                    "thesis": thesis.model_dump() if thesis else None,
                    "opportunities": [item.model_dump() for item in opportunities],
                    "hedges": [item.model_dump() for item in hedges],
                },
                metadata={
                    "horizon_months": [7, 14],
                    "requires_human_review": True,
                    "approval_status": "pending",
                    "source": "mock_workflow",
                },
            )
        ]
        agent_input.context["training_examples"] = examples
        return TrainingDataBuilderAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[
                AgentFinding(
                    title="Training examples built",
                    summary=f"Created {len(examples)} JSON-serializable training example.",
                    evidence=[example.example_id for example in examples],
                    confidence=0.8,
                )
            ],
            training_examples=examples,
        )
