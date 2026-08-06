from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.services.env import load_env

load_env()

ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = ROOT / "prompts" / "scenario_parser_system_prompt.md"


@dataclass
class OllamaParseResult:
    ok: bool
    payload: dict[str, Any] | None
    model: str
    duration_ms: int
    error: str | None = None


class OllamaProvider:
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout_seconds: float = 45.0, retries: int = 1):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.model = model or os.getenv("OLLAMA_SCENARIO_MODEL") or "llama3.1:8b"
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    def health(self) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            payload = response.json()
            models = [item.get("name") for item in payload.get("models", [])]
            return {
                "reachable": True,
                "base_url": self.base_url,
                "selected_model": self.model,
                "model_available": self.model in models,
                "models": models,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "error": None,
            }
        except Exception as exc:
            return {
                "reachable": False,
                "base_url": self.base_url,
                "selected_model": self.model,
                "model_available": False,
                "models": [],
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "error": _safe_error(exc),
            }

    def parse_scenario(self, source_text: str) -> OllamaParseResult:
        started = time.perf_counter()
        prompt = f"{_system_prompt()}\n\nSOURCE TEXT:\n{source_text}\n\nReturn JSON only."
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                response = httpx.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0},
                    },
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                content = payload.get("response", "{}")
                return OllamaParseResult(
                    ok=True,
                    payload=json.loads(content),
                    model=self.model,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            except Exception as exc:
                last_error = _safe_error(exc)
                if attempt < self.retries:
                    time.sleep(0.25 * (2**attempt))
        return OllamaParseResult(
            ok=False,
            payload=None,
            model=self.model,
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=last_error or "Ollama parse failed",
        )


def _system_prompt() -> str:
    return PROMPT_PATH.read_text()


def _safe_error(exc: Exception) -> str:
    return str(exc)[:240] or exc.__class__.__name__
