from app.agents.commodity_agent import SYSTEM_PROMPT, CommodityAgent
from app.models import AgentInput, AgentOutput


class CommoditiesAgentInput(AgentInput):
    """Input schema for the Commodities Agent."""


class CommoditiesAgentOutput(AgentOutput):
    """Output schema for the Commodities Agent."""


class CommoditiesAgent(CommodityAgent):
    name = "Commodities Agent"
    system_prompt = SYSTEM_PROMPT.strip()

