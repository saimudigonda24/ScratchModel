from __future__ import annotations

from typing import Any

from app.models import AgentInput, AgentOutput
from app.services.llm import OpenAIClient


def augment_agent_output_with_openai(agent_name: str, system_prompt: str, agent_input: AgentInput, output: AgentOutput) -> AgentOutput:
    """Attach live OpenAI reasoning provenance while preserving deterministic schemas."""
    client = OpenAIClient()
    signal_lines = [
        f"{signal.source}: {signal.name}={signal.value}; {signal.interpretation}"
        for signal in agent_input.macro_snapshot.signals[:8]
    ]
    finding_lines = [f"{finding.title}: {finding.summary}" for finding in output.findings[:4]]
    opportunity_lines = [f"{item.asset_class}: {item.name}; conviction={item.conviction_score}" for item in output.opportunities[:4]]
    prompt = "\n".join(
        [
            f"Agent: {agent_name}",
            f"Human report title: {agent_input.human_report.title}",
            "Macro signals:",
            *signal_lines,
            "Current structured output:",
            *finding_lines,
            *opportunity_lines,
            "Return a concise audit note: what evidence matters most, what could be wrong, and one human-review question.",
        ]
    )
    response = client.complete(system_prompt, prompt)
    mode = "fallback" if response.used_fallback else "live"
    note = f"OpenAI reasoning provenance ({mode}, {response.model}): {response.content[:700]}"
    if response.error:
        note = f"{note} | provider_error={response.error[:180]}"
    output.notes.append(note)
    return output


def openai_status_probe() -> dict[str, Any]:
    client = OpenAIClient()
    if not client.is_available():
        return {
            "provider": "OpenAI",
            "configured": False,
            "reachable": False,
            "mode": "Fallback",
            "latest_error": "OPENAI_API_KEY missing or HCP_USE_REAL_LLM=false",
        }
    response = client.complete(
        "You are a connection test. Reply with exactly: ok",
        "Confirm the HCP Macro Theme AI OpenAI provider is reachable.",
    )
    return {
        "provider": "OpenAI",
        "configured": True,
        "reachable": not response.used_fallback,
        "mode": "Connected" if not response.used_fallback else "Fallback",
        "latest_error": response.error,
        "model": response.model,
    }
