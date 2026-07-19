from app.connectors import ingest_all_sources
from app.models import AgentFinding, AgentInput, AgentOutput

SYSTEM_PROMPT = """
You are the Data Ingestion Agent for HCP. Normalize live macro, market, policy,
earnings, and positioning data into concise signals with source, direction,
as-of date, and investment interpretation. Preserve provenance.
"""


class DataIngestionAgentInput(AgentInput):
    """Input schema for the Data Ingestion Agent."""


class DataIngestionAgentOutput(AgentOutput):
    """Output schema for the Data Ingestion Agent."""


class DataIngestionAgent:
    name = "Data Ingestion Agent"
    system_prompt = SYSTEM_PROMPT.strip()

    def run(self, agent_input: DataIngestionAgentInput) -> DataIngestionAgentOutput:
        # Future LLM/tool-routing call goes here if ingestion needs reasoning.
        snapshot = ingest_all_sources()
        sources = sorted({signal.source for signal in snapshot.signals})
        return DataIngestionAgentOutput(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            findings=[
                AgentFinding(
                    title="Mock macro source ingestion complete",
                    summary=f"Ingested {len(snapshot.signals)} signals from {len(sources)} configured sources.",
                    evidence=sources,
                    confidence=0.75,
                )
            ],
            notes=["Replace MockJsonConnector with authenticated API clients as keys become available."],
        )
