from app.models import AgentInput, AgentOutput


class BaseAgent:
    name: str
    system_prompt: str

    def run(self, agent_input: AgentInput) -> AgentOutput:
        raise NotImplementedError

