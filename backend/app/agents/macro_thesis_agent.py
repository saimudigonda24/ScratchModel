from app.agents.thesis_generation_agent import SYSTEM_PROMPT, ThesisGenerationAgent
from app.models import AgentInput, AgentOutput


class MacroThesisAgentInput(AgentInput):
    """Input schema for the Macro Thesis Agent."""


class MacroThesisAgentOutput(AgentOutput):
    """Output schema for the Macro Thesis Agent."""


class MacroThesisAgent(ThesisGenerationAgent):
    name = "Macro Thesis Agent"
    system_prompt = SYSTEM_PROMPT.strip()

