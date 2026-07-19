from dataclasses import dataclass
import os
from typing import Any

import httpx

from app.services.env import load_env

load_env()


def real_llm_enabled() -> bool:
    return os.getenv("HCP_USE_REAL_LLM", "false").lower() == "true"


@dataclass
class LLMResponse:
    provider: str
    model: str
    content: str
    raw: dict[str, Any]
    used_fallback: bool = False
    error: str | None = None


class BaseLLMClient:
    provider = "base"
    default_model = "mock"

    def is_available(self) -> bool:
        return False

    def complete(self, system_prompt: str, user_prompt: str, model: str | None = None) -> LLMResponse:
        raise NotImplementedError


class MockLLMClient(BaseLLMClient):
    provider = "mock"
    default_model = "mock-hcp-researcher"

    def __init__(self, slot_name: str = "mock"):
        self.slot_name = slot_name

    def complete(self, system_prompt: str, user_prompt: str, model: str | None = None) -> LLMResponse:
        prompt_excerpt = " ".join(user_prompt.split())[:220]
        content = (
            f"{self.slot_name} fallback view: base case favors slower growth, uneven disinflation, "
            "and selective cross-asset opportunities. Strongest ideas are intermediate duration, "
            "quality equities, gold hedges, and market-neutral alternatives. Weakest reasoning would "
            "ignore labor or credit deterioration triggers."
        )
        return LLMResponse(
            provider=self.slot_name,
            model=model or self.default_model,
            content=content,
            raw={"system_prompt": system_prompt, "prompt_excerpt": prompt_excerpt, "fallback": True},
            used_fallback=True,
        )


class OpenAIClient(BaseLLMClient):
    provider = "openai"
    default_model = "gpt-4o-mini"

    def is_available(self) -> bool:
        return real_llm_enabled() and bool(os.getenv("OPENAI_API_KEY"))

    def complete(self, system_prompt: str, user_prompt: str, model: str | None = None) -> LLMResponse:
        if not self.is_available():
            return MockLLMClient(self.provider).complete(system_prompt, user_prompt, model or self.default_model)
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                json={
                    "model": model or self.default_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                },
                timeout=45,
            )
            response.raise_for_status()
            payload = response.json()
            return LLMResponse(
                provider=self.provider,
                model=model or self.default_model,
                content=payload["choices"][0]["message"]["content"],
                raw=payload,
            )
        except Exception as exc:
            fallback = MockLLMClient(self.provider).complete(system_prompt, user_prompt, model or self.default_model)
            fallback.error = str(exc)
            return fallback


class AnthropicClient(BaseLLMClient):
    provider = "anthropic"
    default_model = "claude-3-5-haiku-latest"

    def is_available(self) -> bool:
        return real_llm_enabled() and bool(os.getenv("ANTHROPIC_API_KEY"))

    def complete(self, system_prompt: str, user_prompt: str, model: str | None = None) -> LLMResponse:
        if not self.is_available():
            return MockLLMClient(self.provider).complete(system_prompt, user_prompt, model or self.default_model)
        try:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model or self.default_model,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.2,
                },
                timeout=45,
            )
            response.raise_for_status()
            payload = response.json()
            content = "\n".join(block.get("text", "") for block in payload.get("content", []))
            return LLMResponse(provider=self.provider, model=model or self.default_model, content=content, raw=payload)
        except Exception as exc:
            fallback = MockLLMClient(self.provider).complete(system_prompt, user_prompt, model or self.default_model)
            fallback.error = str(exc)
            return fallback


class GeminiClient(BaseLLMClient):
    provider = "gemini"
    default_model = "gemini-1.5-flash"

    def is_available(self) -> bool:
        return real_llm_enabled() and bool(os.getenv("GOOGLE_API_KEY"))

    def complete(self, system_prompt: str, user_prompt: str, model: str | None = None) -> LLMResponse:
        if not self.is_available():
            return MockLLMClient(self.provider).complete(system_prompt, user_prompt, model or self.default_model)
        try:
            selected_model = model or self.default_model
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{selected_model}:generateContent",
                params={"key": os.environ["GOOGLE_API_KEY"]},
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": {"temperature": 0.2},
                },
                timeout=45,
            )
            response.raise_for_status()
            payload = response.json()
            parts = payload["candidates"][0]["content"].get("parts", [])
            content = "\n".join(part.get("text", "") for part in parts)
            return LLMResponse(provider=self.provider, model=selected_model, content=content, raw=payload)
        except Exception as exc:
            fallback = MockLLMClient(self.provider).complete(system_prompt, user_prompt, model or self.default_model)
            fallback.error = str(exc)
            return fallback


def default_provider_clients() -> list[BaseLLMClient]:
    return [OpenAIClient(), AnthropicClient(), GeminiClient()]
